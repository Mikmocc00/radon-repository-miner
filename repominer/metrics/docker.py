from .base import BaseMetricsExtractor
from repominer.filters import is_docker_file

# Importiamo dalla tua libreria nativa radon-docker-metrics
from radon_docker_metrics.import_metrics import general_metrics, docker_metrics

METRICS_TO_COMPUTE = tuple(docker_metrics.keys()) + tuple(general_metrics.keys())


class DockerMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        if not script:
            return {}

        results = {}

        # Uniamo tutti i dizionari delle metriche
        all_metrics = {**general_metrics, **docker_metrics}

        for metric_name in METRICS_TO_COMPUTE:
            metric_class = all_metrics.get(metric_name)
            if not metric_class:
                continue

            try:
                results[metric_name] = metric_class(script).count()
            except Exception:
                results[metric_name] = 0  # Fallback in caso di errore

        return results

    def ignore_file(self, path_to_file: str, content: str = None):
        return not is_docker_file(path_to_file, content)