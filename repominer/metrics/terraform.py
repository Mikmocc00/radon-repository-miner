from .base import BaseMetricsExtractor
from repominer.filters import is_terraform_file
from radon_terraform_metrics.import_metrics import general_metrics, configuration_metrics, complex_metrics

METRICS_TO_COMPUTE = (

   "text_entropy",
   "lines_code",
   "num_keys",
   "coupling_score",
   "resource_density",
   "implicit_dependencies",
   "key_density",
   "vocabulary_richness",
   "variable_reference_count",
   "resource_concentration",
   "num_resources",
   "module_fan_in",
   "avg_block_verbosity",
   "max_resources_per_file",
   "lines_comment",

)

class TerraformMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        results = {}

        all_metrics = {**general_metrics, **configuration_metrics, **complex_metrics}

        for metric_name in METRICS_TO_COMPUTE:
            metric_class = all_metrics[metric_name]
            try:
                results[metric_name] = metric_class(script).count()
            except Exception:
                results[metric_name] = 0

        return results

    def ignore_file(self, path_to_file: str, content: str = None):
        return not (
                path_to_file.endswith('.tf')
                or path_to_file.endswith('.tfvars')
                or path_to_file.endswith('.tf.json')
        )