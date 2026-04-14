from .base import BaseMetricsExtractor
from repominer.filters import is_terraform_file
from radon_terraform_metrics.import_metrics import general_metrics, configuration_metrics

METRICS_TO_COMPUTE = (
    'lines_code',
    'resource_density',
    'text_entropy',
    'num_keys',
    'module_fan_in',
    'variable_reference_count',
    'implicit_dependencies',
    'num_tokens',
    'max_resources_per_file',
    'avg_resource_size',
    'num_provisioners',
    'num_locals',
    'change_set_avg',
    'num_dynamic_blocks',
    'resource_type_diversity',
    'change_set_max',
    'num_conditionals',
    'contributors_count',
    'module_reuse_count',
    'num_resources',
    'additions_max',
    'deletions',
    'code_churn_count',
    'additions_avg',
    'highest_contributor_experience'
)

class TerraformMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        results = {}

        all_metrics = {**general_metrics, **configuration_metrics}

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