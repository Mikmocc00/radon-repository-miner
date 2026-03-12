import hcl2
from typing import List
from pydriller.repository import Repository
from pydriller.domain.commit import ModificationType

from repominer import filters, utils
from repominer.mining.base import BaseMiner, FixingCommitClassifier

# Definiamo le "chiavi principali" dei file Terraform da monitorare
CONFIG_TERRAFORM_KEYS = ['resource', 'module', 'variable', 'output', 'provider', 'data', 'locals']

class TerraformMiner(BaseMiner):
    """Estende BaseMiner per mining di repository Terraform"""

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = TerraformFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):
        """Ignora file non Terraform (.tf)"""
        return not path_to_file.endswith('.tf')


class TerraformFixingCommitClassifier(FixingCommitClassifier):
    """Classifica commit che modificano file Terraform rilevanti"""

    def is_data_changed(self) -> bool:
        """Controlla se sono cambiati blocchi significativi (resource/module/variable/output...)"""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type != ModificationType.MODIFY or not modified_file.new_path.endswith('.tf'):
                continue

            try:
                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                data_before = [value for key, value in utils.key_value_list(code_before) if key in CONFIG_TERRAFORM_KEYS]
                data_after = [value for key, value in utils.key_value_list(code_after) if key in CONFIG_TERRAFORM_KEYS]

                return data_before != data_after

            except Exception:
                # HCL malformato o errore di parsing -> ignora
                pass

        return False

    def is_module_changed(self) -> bool:
        """Controlla se sono cambiati i blocchi module"""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type != ModificationType.MODIFY or not modified_file.new_path.endswith('.tf'):
                continue

            try:
                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                modules_before = [value for key, value in utils.key_value_list(code_before) if key == 'module']
                modules_after = [value for key, value in utils.key_value_list(code_after) if key == 'module']

                return modules_before != modules_after

            except Exception:
                pass

        return False

    def is_resource_changed(self) -> bool:
        """Controlla se sono cambiati i blocchi resource"""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type != ModificationType.MODIFY or not modified_file.new_path.endswith('.tf'):
                continue

            try:
                code_before = hcl2.loads(modified_file.source_code_before) if modified_file.source_code_before else {}
                code_after = hcl2.loads(modified_file.source_code) if modified_file.source_code else {}

                resources_before = [value for key, value in utils.key_value_list(code_before) if key == 'resource']
                resources_after = [value for key, value in utils.key_value_list(code_after) if key == 'resource']

                return resources_before != resources_after

            except Exception:
                pass

        return False