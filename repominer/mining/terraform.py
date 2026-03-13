import hcl2
from typing import List
from pydriller.repository import Repository
from pydriller.domain.commit import ModificationType

from repominer import filters, utils
from repominer.mining.base import BaseMiner, FixingCommitClassifier

# Definiamo le "chiavi principali" dei file Terraform da monitorare
CONFIG_TERRAFORM_KEYS = [
    'resource',
    'module',
    'variable',
    'output',
    'provider',
    'data',
    'locals',
    'terraform'
]

class TerraformMiner(BaseMiner):
    """Estende BaseMiner per mining di repository Terraform"""

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = TerraformFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):
        if not path_to_file:
            return True
        return not path_to_file.endswith((".tf", ".tfvars"))


class TerraformFixingCommitClassifier(FixingCommitClassifier):
    """Classifica commit che modificano file Terraform rilevanti"""

    def is_data_changed(self) -> bool:
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

            try:
                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                data_before = [v for k,v in utils.key_value_list(code_before) if k in CONFIG_TERRAFORM_KEYS]
                data_after = [v for k,v in utils.key_value_list(code_after) if k in CONFIG_TERRAFORM_KEYS]

                if data_before != data_after:
                    return True

            except Exception:
                pass

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

            try:

                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                modules_before = [v for k,v in utils.key_value_list(code_before) if k == "module"]
                modules_after = [v for k,v in utils.key_value_list(code_after) if k == "module"]

                if modules_before != modules_after:
                    return True

            except Exception:
                pass

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

            try:

                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                resources_before = [v for k,v in utils.key_value_list(code_before) if k == "resource"]
                resources_after = [v for k,v in utils.key_value_list(code_after) if k == "resource"]

                if resources_before != resources_after:
                    return True

            except Exception:
                pass

        return False