import os
import nltk
import re

from typing import Dict, Generator, List

from pydriller.domain.commit import Commit, ModificationType
from pydriller.repository import Git, Repository

from repominer import utils
from repominer.files import FixedFile, FailureProneFile
from repominer.mining import rules

# Important: downloading resources for NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Constants
full_name_pattern = re.compile(r'(github|gitlab){1}\.com/([\w\W]+)$')


class BaseMiner:
    """
    This is the base class to mine a software repository for:

    * defect-fixing commits
    * files fixed by defect-fixing commits (i.e., fixed-files)
    * failure-prone files
    """

    def __init__(self,
                 url_to_repo: str,
                 clone_repo_to: str,
                 branch: str = None):
        """
        The class constructor.
        Initialize a new BaseMiner.
        """

        # Extract repository full name from URL
        full_name_match = full_name_pattern.search(url_to_repo.replace('.git', ''))
        if not full_name_match:
            raise ValueError(
                'Insert a valid Git URL. For example: '
                'https://github.com/radon-h2020/radon-repository-miner.git'
            )

        # Ensure the target folder exists
        if not os.path.isdir(clone_repo_to):
            raise FileNotFoundError(f'{clone_repo_to} does not exist.')

        # Path where the repository will be cloned
        self.path_to_repo = os.path.join(clone_repo_to, full_name_match.groups()[1].split('/')[1])
        self.branch = branch

        # Initialize lists
        self.fixing_commits = list()
        self.fixed_files = list()

        # Clone the repository if it does not exist locally
        if not os.path.exists(self.path_to_repo):
            from git import Repo
            Repo.clone_from(
                url_to_repo,
                self.path_to_repo,
                branch=self.branch,
                depth=None,  # full clone
                multi_options=['--no-single-branch']
            )

        # Get all commits sorted by commit date
        self.commit_hashes = [c.hash for c in
                              Repository(
                                  path_to_repo=self.path_to_repo,
                                  only_in_branch=self.branch,
                                  order='date-order',
                                  num_workers=1
                              ).traverse_commits()]

        # Classifier to determine fixing commit categories
        self.FixingCommitClassifier = FixingCommitClassifier

    def discard_undesired_fixing_commits(self, commits: List[str]) -> None:
        """
        Discard undesired commits.
        Note, the update occurs in-place.
        """
        if not commits:
            return

        self.sort_commits(commits)

        for commit in Repository(self.path_to_repo,
                                 from_commit=commits[0],
                                 to_commit=commits[-1],
                                 only_in_branch=self.branch).traverse_commits():
            i = 0
            while i < len(commit.modified_files):
                if commit.modified_files[i].change_type != ModificationType.MODIFY:
                    i += 1
                elif self.ignore_file(commit.modified_files[i].new_path, commit.modified_files[i].source_code):
                    i += 1
                else:
                    break

            if i == len(commit.modified_files) and commit.hash in commits:
                commits.remove(commit.hash)

    def get_fixing_commits(self, num_workers=8) -> Dict[str, List[str]]:
        """
        Return a list of bug-fixing commit hash categorized by type.
        """
        commits_labels = {}
        commits = []

        for commit in Repository(self.path_to_repo, only_in_branch=self.branch, num_workers=num_workers).traverse_commits():

            if commit.hash in self.fixing_commits:
                continue

            fcc = self.FixingCommitClassifier(commit)

            if fcc.fixes_conditional():
                commits_labels.setdefault(commit.hash, []).append('CONDITIONAL')
            if fcc.fixes_configuration_data():
                commits_labels.setdefault(commit.hash, []).append('CONFIGURATION_DATA')
            if fcc.fixes_dependency():
                commits_labels.setdefault(commit.hash, []).append('DEPENDENCY')
            if fcc.fixes_documentation():
                commits_labels.setdefault(commit.hash, []).append('DOCUMENTATION')
            if fcc.fixes_idempotency():
                commits_labels.setdefault(commit.hash, []).append('IDEMPOTENCY')
            if fcc.fixes_security():
                commits_labels.setdefault(commit.hash, []).append('SECURITY')
            if fcc.fixes_service():
                commits_labels.setdefault(commit.hash, []).append('SERVICE')
            if fcc.fixes_syntax():
                commits_labels.setdefault(commit.hash, []).append('SYNTAX')

            if commit.hash in commits_labels:
                commits.append(commit.hash)

        if commits:
            self.discard_undesired_fixing_commits(commits)
            self.fixing_commits.extend(commits)
            self.sort_commits(self.fixing_commits)

            for sha in list(commits_labels.keys()):
                if sha not in commits:
                    del commits_labels[sha]

        return commits_labels

    def get_fixed_files(self) -> None:
        """
        Populate the list of FixedFile objects using the SZZ algorithm.
        """
        if not self.fixing_commits:
            return

        self.sort_commits(self.fixing_commits)
        self.fixed_files = list()
        renamed_files = dict()
        git_repo = Git(self.path_to_repo)

        if len(self.fixing_commits) == 1:
            repository_mining = Repository(self.path_to_repo, single=self.fixing_commits[0],
                                           only_in_branch=self.branch, num_workers=1)
        else:
            repository_mining = Repository(self.path_to_repo,
                                           from_commit=self.fixing_commits[-1],
                                           to_commit=self.fixing_commits[0],
                                           order='reverse',
                                           only_in_branch=self.branch,
                                           num_workers=1)

        for commit in repository_mining.traverse_commits():
            for modified_file in commit.modified_files:
                if modified_file.change_type not in (ModificationType.MODIFY, ModificationType.RENAME):
                    continue

                if modified_file.change_type == ModificationType.RENAME:
                    renamed_files[modified_file.old_path] = renamed_files.get(modified_file.new_path,
                                                                              modified_file.new_path)

                if commit.hash not in self.fixing_commits:
                    continue

                if self.ignore_file(modified_file.new_path, modified_file.source_code):
                    continue

                bug_inducing_commits = git_repo.get_commits_last_modified_lines(commit, modified_file)

                if not bug_inducing_commits.get(modified_file.new_path):
                    continue
                else:
                    bic_list = list(bug_inducing_commits[modified_file.new_path])
                    self.sort_commits(bic_list)
                    bic = bic_list[0]

                current_fix = FixedFile(filepath=renamed_files.get(modified_file.new_path, modified_file.new_path),
                                        bic=bic,
                                        fic=commit.hash)

                if current_fix not in self.fixed_files:
                    self.fixed_files.append(current_fix)
                else:
                    idx = self.fixed_files.index(current_fix)
                    existing_fix = self.fixed_files[idx]

                    if self.commit_hashes.index(current_fix.fic) < self.commit_hashes.index(existing_fix.bic):
                        if modified_file.new_path in renamed_files:
                            del renamed_files[modified_file.new_path]
                        current_fix.filepath = modified_file.new_path
                        self.fixed_files.append(current_fix)
                    elif self.commit_hashes.index(current_fix.bic) < self.commit_hashes.index(existing_fix.bic):
                        existing_fix.bic = current_fix.bic

    def ignore_file(self, path_to_file: str, content: str = None) -> bool:
        return False

    def label(self) -> Generator[FailureProneFile, None, None]:
        if not (self.fixing_commits and self.fixed_files):
            return

        self.sort_commits(self.fixing_commits)
        renamed_files = {}

        for commit in Repository(self.path_to_repo, from_commit=self.fixing_commits[-1],
                                 to_commit=self.commit_hashes[0],
                                 order='reverse', num_workers=1).traverse_commits():

            for file in self.fixed_files:
                idx_fic = self.commit_hashes.index(file.fic)
                idx_bic = self.commit_hashes.index(file.bic)
                idx_commit = self.commit_hashes.index(commit.hash)

                if idx_fic > idx_commit >= idx_bic:
                    yield FailureProneFile(filepath=renamed_files.get(file.filepath, file.filepath),
                                           commit=commit.hash,
                                           fixing_commit=file.fic)

            for modified_file in commit.modified_files:
                if modified_file.change_type == ModificationType.RENAME:
                    renamed_files[modified_file.new_path] = modified_file.old_path

    def sort_commits(self, commits: List[str]) -> None:
        sorted_commits = [sha for sha in self.commit_hashes if sha in commits]
        commits.clear()
        commits.extend(sorted_commits)


class FixingCommitClassifier:
    def __init__(self, commit: Commit):
        if commit is None:
            raise TypeError('Expected a pydriller.domain.commit.Commit object.')

        self.commit = commit
        self.sentences = []

        for sentence in nltk.sent_tokenize(commit.msg):
            tokens = [word.strip() for word in nltk.tokenize.word_tokenize(sentence) if word.isalpha()]
            self.sentences.append(tokens)

    def is_comment_changed(self) -> bool:
        for modified_file in self.commit.modified_files:
            if modified_file.change_type != ModificationType.MODIFY:
                continue
            diff = [line.strip() for _, line in modified_file.diff_parsed.get('added', {})]
            diff.extend([line.strip() for _, line in modified_file.diff_parsed.get('deleted', {})])
            if any(line.startswith('#') for line in diff):
                return True
        return False

    def is_data_changed(self) -> bool: return False
    def is_include_changed(self) -> bool: return False
    def is_service_changed(self) -> bool: return False

    def _check_rules(self, rule_func, extra_cond=False):
        for sentence in self.sentences:
            s_text = ' '.join(sentence)
            s_dep = ' '.join(utils.get_head_dependents(s_text))
            if rules.has_defect_pattern(s_text) and (rule_func(s_dep) or extra_cond):
                return True
        return False

    def fixes_conditional(self):
        return self._check_rules(rules.has_conditional_pattern)

    def fixes_configuration_data(self):
        for sentence in self.sentences:
            s_text = ' '.join(sentence)
            s_dep = ' '.join(utils.get_head_dependents(s_text))
            if rules.has_defect_pattern(s_text) and (
                    rules.has_storage_configuration_pattern(s_dep) or
                    rules.has_file_configuration_pattern(s_dep) or
                    rules.has_network_configuration_pattern(s_dep) or
                    rules.has_user_configuration_pattern(s_dep) or
                    rules.has_cache_configuration_pattern(s_dep) or
                    self.is_data_changed()):
                return True
        return False

    def fixes_dependency(self):
        return self._check_rules(rules.has_dependency_pattern, self.is_include_changed())

    def fixes_documentation(self):
        return self._check_rules(rules.has_documentation_pattern, self.is_comment_changed())

    def fixes_idempotency(self):
        return self._check_rules(rules.has_idempotency_pattern)

    def fixes_security(self):
        return self._check_rules(rules.has_security_pattern)

    def fixes_service(self):
        return self._check_rules(rules.has_service_pattern, self.is_service_changed())

    def fixes_syntax(self):
        return self._check_rules(rules.has_syntax_pattern)