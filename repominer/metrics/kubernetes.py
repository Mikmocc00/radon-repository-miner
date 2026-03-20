from .base import BaseMetricsExtractor
from repominer.filters import is_kubernetes_file
from radon_kubernetes_metrics.import_metrics import general_metrics, configuration_metrics


# Unione metriche
ALL_METRICS = {**general_metrics, **configuration_metrics}
METRICS_TO_COMPUTE = tuple(ALL_METRICS.keys())


class KubernetesMetricsExtractor(BaseMetricsExtractor):

    # -----------------------------
    # PRODUCT METRICS (ROBUSTO)
    # -----------------------------
    def get_product_metrics(self, script: str) -> dict:

        results = {}

        # protezione base
        if not script or not isinstance(script, str):
            return {metric: 0 for metric in METRICS_TO_COMPUTE}

        for metric_name in METRICS_TO_COMPUTE:

            metric_class = ALL_METRICS.get(metric_name)

            if metric_class is None:
                results[metric_name] = 0
                continue

            try:
                value = metric_class(script).count()

                # normalizza output strani
                if value is None:
                    value = 0
                elif isinstance(value, (int, float)):
                    pass
                else:
                    value = 0

                results[metric_name] = value

            except Exception as e:
                # NON rompere mai la pipeline
                print(f"[K8sMetrics] Error in metric {metric_name}: {e}")
                results[metric_name] = 0

        return results

    # -----------------------------
    # FILE FILTER (MOLTO IMPORTANTE)
    # -----------------------------
    def ignore_file(self, path_to_file: str, content: str = None):

        # sicurezza base
        if not path_to_file:
            return True

        # filtro veloce per estensione (evita chiamate pesanti)
        if not path_to_file.endswith((".yml", ".yaml", ".json")):
            return True

        # file troppo piccoli o vuoti → inutili
        if not content or len(content.strip()) < 10:
            return True

        # filtro principale
        try:
            if is_kubernetes_file(path_to_file, content):
                return False
        except Exception:
            pass

        # fallback intelligente (IMPORTANTISSIMO)
        # molti repo k8s non passano il filtro ufficiale
        lowered = content.lower()

        if any(k in lowered for k in (
                "apiVersion",
                "kind:",
                "metadata:",
                "spec:"
        )):
            return False

        return True