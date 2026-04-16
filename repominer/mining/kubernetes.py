import yaml
import re
from pydriller.domain.commit import ModificationType
from typing import Set, Tuple

from repominer import filters
from repominer.mining.base import BaseMiner, FixingCommitClassifier

# Kubernetes bug keywords
KUBERNETES_DEFECT_KEYWORDS = {
    "fix", "bug", "error", "issue", "fail",
    "failure", "crash", "incorrect", "wrong",
    "invalid", "broken", "crashloopbackoff", "oomkilled",
    "evicted"
}

KUBERNETES_CONTEXT_KEYWORDS = {
    "pod", "deployment", "service", "ingress",
    "configmap", "secret", "statefulset", "daemonset",
    "rbac", "rolebinding", "pvc", "volume", "namespace",
    "replicaset", "clusterrole", "nodeport"
}


class KubernetesMiner(BaseMiner):
    """ This class extends BaseMiner to mine Kubernetes-based repositories
    """

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = KubernetesFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):
        """
        Ignore non-Kubernetes files.
        """
        return not filters.is_kubernetes_file(path_to_file, content)


class KubernetesFixingCommitClassifier(FixingCommitClassifier):

    # -----------------------------
    # linguistic detection
    # -----------------------------

    def _has_kubernetes_bug_pattern(self, sentence: str) -> bool:
        sentence = sentence.lower()

        has_bug = any(k in sentence for k in KUBERNETES_DEFECT_KEYWORDS)
        has_context = any(k in sentence for k in KUBERNETES_CONTEXT_KEYWORDS)

        return has_bug and has_context

    def _has_issue_reference(self, sentence: str) -> bool:
        return bool(re.search(r"(fix(e[sd])?|close[sd]?|resolve[sd]?)\s+#\d+", sentence.lower()))

    # -----------------------------
    # parsing
    # -----------------------------

    def _parse_yaml_docs(self, source) -> list:
        """Parses multiple YAML documents from a single string/file."""
        if not source:
            return []
        try:
            # list() converts the generator from safe_load_all to a list of dicts
            return list(yaml.safe_load_all(source))
        except yaml.YAMLError:
            return []

    # -----------------------------
    # extractors
    # -----------------------------

    def _extract_kinds(self, parsed_docs: list) -> Set[str]:
        """Extracts the 'kind' of all resources in the file."""
        kinds = set()
        for doc in parsed_docs:
            if isinstance(doc, dict) and "kind" in doc:
                kinds.add(doc["kind"])
        return kinds

    def _extract_images(self, parsed_docs: list) -> Set[str]:
        """Extracts container images to check for version/dependency fixes."""
        images = set()
        for doc in parsed_docs:
            if not isinstance(doc, dict):
                continue

            # Simple recursive search for the 'image' key
            def find_images(d):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k == "image" and isinstance(v, str):
                            images.add(v)
                        else:
                            find_images(v)
                elif isinstance(d, list):
                    for item in d:
                        find_images(item)

            find_images(doc)
        return images

    # -----------------------------
    # semantic change detection
    # -----------------------------

    # -----------------------------
    # semantic change detection
    # -----------------------------

    def is_service_changed(self) -> bool:
        """Checks if the actual structure or kind of the resource changed."""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type not in (ModificationType.MODIFY, ModificationType.ADD,
                                                 ModificationType.DELETE):
                continue

            path = modified_file.new_path or modified_file.old_path

            # FIX: Intercettiamo i file mancanti (sottomoduli, Git LFS o commit corrotti)
            try:
                source_code = modified_file.source_code
                source_code_before = modified_file.source_code_before
            except ValueError:
                # Se l'hash non viene risolto, ignoriamo il file e passiamo al prossimo
                continue

            # Usa le variabili appena estratte al posto di richiamare le property
            if not filters.is_kubernetes_file(path, source_code):
                continue

            code_before = self._parse_yaml_docs(source_code_before)
            code_after = self._parse_yaml_docs(source_code)

            kinds_before = self._extract_kinds(code_before)
            kinds_after = self._extract_kinds(code_after)

            if kinds_before != kinds_after:
                return True

        return False

    def is_dependency_changed(self) -> bool:
        """Checks if container images (dependencies) changed."""
        for modified_file in self.commit.modified_files:
            if modified_file.change_type not in (ModificationType.MODIFY, ModificationType.ADD,
                                                 ModificationType.DELETE):
                continue

            path = modified_file.new_path or modified_file.old_path

            # FIX: Intercettiamo i file mancanti (sottomoduli, Git LFS o commit corrotti)
            try:
                source_code = modified_file.source_code
                source_code_before = modified_file.source_code_before
            except ValueError:
                # Se l'hash non viene risolto, ignoriamo il file e passiamo al prossimo
                continue

            # Usa le variabili appena estratte al posto di richiamare le property
            if not filters.is_kubernetes_file(path, source_code):
                continue

            code_before = self._parse_yaml_docs(source_code_before)
            code_after = self._parse_yaml_docs(source_code)

            images_before = self._extract_images(code_before)
            images_after = self._extract_images(code_after)

            if images_before != images_after:
                return True

        return False
    # -----------------------------
    # override base classifiers
    # -----------------------------

    def fixes_dependency(self):
        if self.is_dependency_changed():
            return True

        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_kubernetes_bug_pattern(sentence):
                return True
            if self._has_issue_reference(sentence):
                return True

        return super().fixes_dependency()

    def fixes_service(self):
        if self.is_service_changed():
            return True

        for sentence in self.sentences:
            sentence = ' '.join(sentence)
            if self._has_kubernetes_bug_pattern(sentence):
                return True
            if self._has_issue_reference(sentence):
                return True

        return super().fixes_service()