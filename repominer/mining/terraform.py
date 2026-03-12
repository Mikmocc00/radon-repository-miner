import hcl2
from typing import List, Any

from pydriller.domain.commit import ModificationType

from repominer import utils
from repominer.mining.base import BaseMiner, FixingCommitClassifier


CONFIG_TERRAFORM_KEYS = [
    "resource",
    "module",
    "variable",
    "output",
    "provider",
    "data",
    "locals",
]


class TerraformMiner(BaseMiner):
    """Extends BaseMiner to mine Terraform-based repositories."""

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = TerraformFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None) -> bool:
        """Ignore non-Terraform files."""
        return not path_to_file.endswith(".tf")


class TerraformFixingCommitClassifier(FixingCommitClassifier):
    """Classifies bug-fixing commits in Terraform files."""

    # -------------------------
    # Utility helpers
    # -------------------------

    def _parse_hcl(self, code: str) -> dict:
        """Safely parse HCL code."""
        if not code:
            return {}

        try:
            return hcl2.loads(code)
        except Exception:
            return {}

    def _extract_blocks(self, parsed_code: dict, keys: List[str]) -> List[Any]:
        """Extract specific Terraform blocks."""
        return [
            value
            for key, value in utils.key_value_list(parsed_code)
            if key in keys
        ]

    def _terraform_files(self):
        """Yield modified Terraform files."""
        for modified_file in self.commit.modified_files:

            if (
                    modified_file.change_type == ModificationType.MODIFY
                    and modified_file.new_path
                    and modified_file.new_path.endswith(".tf")
            ):
                yield modified_file

    def _is_block_changed(self, keys: List[str]) -> bool:
        """Generic comparison for Terraform blocks."""

        for modified_file in self._terraform_files():

            code_before = self._parse_hcl(modified_file.source_code_before)
            code_after = self._parse_hcl(modified_file.source_code)

            blocks_before = self._extract_blocks(code_before, keys)
            blocks_after = self._extract_blocks(code_after, keys)

            if blocks_before != blocks_after:
                return True

        return False

    # -------------------------
    # Public classification API
    # -------------------------

    def is_data_changed(self) -> bool:
        """Check if Terraform configuration blocks changed."""
        return self._is_block_changed(CONFIG_TERRAFORM_KEYS)

    def is_module_changed(self) -> bool:
        """Check if module blocks changed."""
        return self._is_block_changed(["module"])

    def is_resource_changed(self) -> bool:
        """Check if resource blocks changed."""
        return self._is_block_changed(["resource"])

    def is_locals_changed(self) -> bool:
        """Check if locals blocks changed."""
        return self._is_block_changed(["locals"])

    def is_provider_changed(self) -> bool:
        """Check if provider blocks changed."""
        return self._is_block_changed(["provider"])

    def is_datasource_changed(self) -> bool:
        """Check if data blocks changed."""
        return self._is_block_changed(["data"])

    def is_output_changed(self) -> bool:
        """Check if output blocks changed."""
        return self._is_block_changed(["output"])

    def is_variable_changed(self) -> bool:
        """Check if variable blocks changed."""
        return self._is_block_changed(["variable"])