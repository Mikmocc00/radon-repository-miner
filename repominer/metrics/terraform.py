from .base import BaseMetricsExtractor
from repominer.filters import is_terraform_file


class TerraformMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:

        lines = script.splitlines()

        return {
            "lines_code": len(lines),
            "num_resources": script.count("resource"),
            "num_variables": script.count("variable"),
            "num_providers": script.count("provider")
        }

    def ignore_file(self, path_to_file: str, content: str = None):
        return not is_terraform_file(path_to_file)