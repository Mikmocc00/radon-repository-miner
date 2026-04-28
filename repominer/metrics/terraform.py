from .base import BaseMetricsExtractor
from radon_terraform_metrics.import_metrics import general_metrics, configuration_metrics, complex_metrics

METRICS_TO_COMPUTE = (
    'text_entropy',
    'num_keys',
    'vocabulary_richness',
    'lines_code',
    'module_fan_in',
    'implicit_dependencies',
    'num_conditionals',
    'resource_type_diversity',
    'variable_reference_count',
    'coupling_score',
    'resource_density',
    'dynamic_complexity',
    'avg_block_verbosity'
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