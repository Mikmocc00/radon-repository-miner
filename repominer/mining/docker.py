import re
from typing import Set, List
from pydriller.domain.commit import ModificationType

from repominer import filters
from repominer.mining.base import BaseMiner, FixingCommitClassifier


DOCKER_DEFECT_KEYWORDS = {
    "fix", "bug", "error", "issue", "fail",
    "failure", "crash", "incorrect", "wrong",
    "invalid", "broken", "vulnerability", "cve", "size",
    "leak", "permission", "root", "timeout", "denied"
}

DOCKER_CONTEXT_KEYWORDS = {
    "dockerfile", "image", "container", "build", "layer",
    "volume", "expose", "entrypoint", "cmd", "env", "run", "cache",
    "from", "workdir", "user", "arg", "healthcheck"
}


class DockerMiner(BaseMiner):
    """ This class extends BaseMiner to mine Docker-based repositories """

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = DockerFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):
        """ Ignore non-Docker files. """
        return not filters.is_docker_file(path_to_file, content)


class DockerFixingCommitClassifier(FixingCommitClassifier):

  

    def _has_docker_bug_pattern(self, sentence: str) -> bool:
        sentence = sentence.lower()
        has_bug = any(k in sentence for k in DOCKER_DEFECT_KEYWORDS)
        has_context = any(k in sentence for k in DOCKER_CONTEXT_KEYWORDS)
        return has_bug and has_context

    def _has_issue_reference(self, sentence: str) -> bool:
        return bool(re.search(r"(fix(e[sd])?|close[sd]?|resolve[sd]?)\s+#\d+", sentence.lower()))

  

    def _extract_base_images(self, source: str) -> Set[str]:
        """Extracts the base images from FROM instructions."""
        if not source:
            return set()

        images = set()
        for line in source.split('\n'):
            line = line.strip()
            if line.upper().startswith('FROM '):
                parts = line.split()
                if len(parts) > 1:
                    images.add(parts[1])
        return images

    def _extract_instructions(self, source: str, instruction_names: List[str]) -> Set[str]:
        """Generic extractor for specific Docker instructions (e.g., CMD, ENV, USER)."""
        if not source:
            return set()

        extracted = set()
        for line in source.split('\n'):
            line = line.strip()
            for inst in instruction_names:
                if line.upper().startswith(f"{inst} "):
                    extracted.add(line)
        return extracted

   

    def _has_file_changed_semantically(self, extractor_func, *args) -> bool:
        """Helper to avoid repeating the loop over modified_files."""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type not in (ModificationType.MODIFY, ModificationType.ADD,
                                                 ModificationType.DELETE):
                continue

            path = modified_file.new_path or modified_file.old_path

            try:
                source_code = modified_file.source_code
                source_code_before = modified_file.source_code_before
            except ValueError:
                continue

            if not filters.is_docker_file(path, source_code):
                continue

            before = extractor_func(source_code_before, *args)
            after = extractor_func(source_code, *args)

            if before != after:
                return True

        return False

    def is_dependency_changed(self) -> bool:
        """Check if base images (FROM) are modified."""
        return self._has_file_changed_semantically(self._extract_base_images)

    def is_service_changed(self) -> bool:
        """Check if execution commands (CMD, ENTRYPOINT, HEALTHCHECK) are modified."""
        return self._has_file_changed_semantically(self._extract_instructions, ['CMD', 'ENTRYPOINT', 'HEALTHCHECK'])

    def is_configuration_data_changed(self) -> bool:
        """Check if environments or metadata (ENV, ARG, EXPOSE, VOLUME, WORKDIR) are modified."""
        return self._has_file_changed_semantically(self._extract_instructions,
                                                   ['ENV', 'ARG', 'EXPOSE', 'VOLUME', 'WORKDIR'])

    def is_security_changed(self) -> bool:
        """Check if user execution context (USER) is modified."""
        return self._has_file_changed_semantically(self._extract_instructions, ['USER'])


    def fixes_dependency(self):
        if self.is_dependency_changed():
            return True
        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_docker_bug_pattern(sentence) or self._has_issue_reference(sentence):
                return True
        return super().fixes_dependency()

    def fixes_service(self):
        if self.is_service_changed():
            return True
        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_docker_bug_pattern(sentence) or self._has_issue_reference(sentence):
                return True
        return super().fixes_service()

    def fixes_configuration_data(self):
        if self.is_configuration_data_changed():
            return True
        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_docker_bug_pattern(sentence) or self._has_issue_reference(sentence):
                return True
        return super().fixes_configuration_data()

    def fixes_security(self):
        if self.is_security_changed():
            return True
        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_docker_bug_pattern(sentence) or self._has_issue_reference(sentence):
                return True
        return super().fixes_security()
