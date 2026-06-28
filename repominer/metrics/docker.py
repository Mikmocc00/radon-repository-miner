from .base import BaseMetricsExtractor
from repominer.filters import is_docker_file

from radon_docker_metrics.import_metrics import general_metrics, docker_metrics

METRICS_TO_COMPUTE = (
    'runs_as_root',
    'num_volumes',
    'avg_run_commands_per_layer',
    'attack_surface',
    'parameterization_density',
    'num_args',
    'has_entrypoint',
    'text_entropy',
    'num_exposed_ports',
    'num_from_instructions',
    'dockerfile_lines',
    'security_density',
    'num_copy_instructions',
    'num_keys',
    'reproducibility_risk',
    'num_unpinned_versions',
    'config_entropy_ratio',
    'num_hardcoded_ips'
)

class DockerMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        if not script:
            return {}

        results = {}

        all_metrics = {**general_metrics, **docker_metrics}

        for metric_name in METRICS_TO_COMPUTE:
            metric_class = all_metrics.get(metric_name)
            if not metric_class:
                continue

            try:
                results[metric_name] = metric_class(script).count()
            except Exception:
                results[metric_name] = 0

        return results

    def ignore_file(self, path_to_file: str, content: str = None):
        return not is_docker_file(path_to_file, content)