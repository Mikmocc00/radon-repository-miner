import hcl2
import re
from typing import Set, Tuple
from pydriller.domain.commit import ModificationType

from repominer.mining.base import BaseMiner, FixingCommitClassifier


# attributi poco rilevanti per bug fixing
IGNORED_ATTRIBUTES = {
    "tags",
    "description",
    "name",
    "comment"
}

DATA_KEYS = ["variable", "locals", "output"]


# Terraform bug keywords
TERRAFORM_DEFECT_KEYWORDS = {
    "fix", "bug", "error", "issue", "fail",
    "failure", "crash", "incorrect", "wrong",
    "invalid", "broken"
}

TERRAFORM_CONTEXT_KEYWORDS = {
    "provider", "module", "resource",
    "variable", "output", "state",
    "plan", "apply", "dependency"
}


class TerraformMiner(BaseMiner):

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = TerraformFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):

        if not path_to_file:
            return True

        return not path_to_file.endswith((".tf", ".tfvars"))


class TerraformFixingCommitClassifier(FixingCommitClassifier):

    # -----------------------------
    # linguistic detection
    # -----------------------------

    def _has_terraform_bug_pattern(self, sentence: str) -> bool:

        sentence = sentence.lower()

        has_bug = any(k in sentence for k in TERRAFORM_DEFECT_KEYWORDS)
        has_context = any(k in sentence for k in TERRAFORM_CONTEXT_KEYWORDS)

        return has_bug and has_context

    def _has_issue_reference(self, sentence: str) -> bool:

        return bool(re.search(r"(fix(e[sd])?|close[sd]?|resolve[sd]?)\s+#\d+", sentence.lower()))

    # -----------------------------
    # parsing
    # -----------------------------

    def _parse_hcl(self, source):

        if not source:
            return {}

        try:
            return hcl2.loads(source)
        except Exception:
            return {}

    # -----------------------------
    # extractors
    # -----------------------------

    def _extract_resources(self, parsed) -> Set[Tuple[str, str]]:

        resources = set()

        for block in parsed.get("resource", []):
            for rtype in block:
                for name in block[rtype]:
                    resources.add((rtype, name))

        return resources

    def _extract_resource_attributes(self, parsed):

        attributes = set()

        for block in parsed.get("resource", []):

            for rtype in block:
                for name in block[rtype]:

                    body = block[rtype][name]

                    if isinstance(body, dict):

                        for attr in body:

                            if attr not in IGNORED_ATTRIBUTES:
                                attributes.add((rtype, name, attr))

        return attributes

    def _extract_modules(self, parsed):

        modules = set()

        for block in parsed.get("module", []):
            for name in block:
                modules.add(name)

        return modules

    def _extract_providers(self, parsed):

        providers = set()

        for block in parsed.get("provider", []):
            for name in block:
                providers.add(name)

        return providers

    def _extract_data(self, parsed):

        data = set()

        for key in DATA_KEYS:

            for block in parsed.get(key, []):
                for name in block:
                    data.add((key, name))

        return data

    # -----------------------------
    # semantic change detection
    # -----------------------------

    def is_data_changed(self) -> bool:

        for modified_file in self.commit.modified_files:

            if modified_file.change_type not in (
                    ModificationType.MODIFY,
                    ModificationType.ADD,
                    ModificationType.DELETE
            ):
                continue

            path = modified_file.new_path or modified_file.old_path

            if not path or not path.endswith((".tf", ".tfvars")):
                continue

            code_before = self._parse_hcl(modified_file.source_code_before)
            code_after = self._parse_hcl(modified_file.source_code)

            data_before = self._extract_data(code_before)
            data_after = self._extract_data(code_after)

            if data_before != data_after:
                return True

        return False

    def is_module_changed(self) -> bool:

        for modified_file in self.commit.modified_files:

            if modified_file.change_type not in (
                    ModificationType.MODIFY,
                    ModificationType.ADD,
                    ModificationType.DELETE
            ):
                continue

            path = modified_file.new_path or modified_file.old_path

            if not path or not path.endswith(".tf"):
                continue

            code_before = self._parse_hcl(modified_file.source_code_before)
            code_after = self._parse_hcl(modified_file.source_code)

            modules_before = self._extract_modules(code_before)
            modules_after = self._extract_modules(code_after)

            if modules_before != modules_after:
                return True

            providers_before = self._extract_providers(code_before)
            providers_after = self._extract_providers(code_after)

            if providers_before != providers_after:
                return True

        return False

    def is_resource_changed(self) -> bool:

        for modified_file in self.commit.modified_files:

            if modified_file.change_type not in (
                    ModificationType.MODIFY,
                    ModificationType.ADD,
                    ModificationType.DELETE
            ):
                continue

            path = modified_file.new_path or modified_file.old_path

            if not path or not path.endswith(".tf"):
                continue

            code_before = self._parse_hcl(modified_file.source_code_before)
            code_after = self._parse_hcl(modified_file.source_code)

            resources_before = self._extract_resources(code_before)
            resources_after = self._extract_resources(code_after)

            if resources_before != resources_after:
                return True

            attrs_before = self._extract_resource_attributes(code_before)
            attrs_after = self._extract_resource_attributes(code_after)

            if attrs_before != attrs_after:
                return True

        return False

    # -----------------------------
    # semantic bug detection
    # -----------------------------

    def fixes_terraform_semantic(self) -> bool:

        if self.is_resource_changed():
            return True

        if self.is_module_changed():
            return True

        if self.is_data_changed():
            return True

        return False

    # -----------------------------
    # override base classifiers
    # -----------------------------

    def fixes_configuration_data(self):

        if self.is_data_changed():
            return True

        for sentence in self.sentences:

            sentence = ' '.join(sentence)

            if self._has_terraform_bug_pattern(sentence):
                return True

            if self._has_issue_reference(sentence):
                return True

        return super().fixes_configuration_data()

    def fixes_dependency(self):

        if self.is_module_changed():
            return True

        for sentence in self.sentences:

            sentence = ' '.join(sentence)

            if self._has_terraform_bug_pattern(sentence):
                return True

        return super().fixes_dependency()

    def fixes_service(self):

        if self.is_resource_changed():
            return True

        for sentence in self.sentences:

            sentence = ' '.join(sentence)

            if self._has_terraform_bug_pattern(sentence):
                return True

        return super().fixes_service()