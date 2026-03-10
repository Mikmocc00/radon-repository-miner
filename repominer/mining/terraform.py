from repominer.mining.base import BaseMiner
from repominer import filters


class TerraformMiner(BaseMiner):
    """
    Miner for Terraform repositories
    """

    def ignore_file(self, path_to_file: str, content: str = None):
        return not filters.is_terraform_file(path_to_file)