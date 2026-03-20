import yaml
import re
from typing import Set
from pydriller.domain.commit import ModificationType

from repominer import filters
from repominer.mining.base import BaseMiner, FixingCommitClassifier


# -----------------------------
# KEYWORDS
# -----------------------------

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


# -----------------------------
# MINER
# -----------------------------

class KubernetesMiner(BaseMiner):

    def __init__(self, url_to_repo: str, clone_repo_to: str, branch: str = None):
        super().__init__(url_to_repo, clone_repo_to, branch)
        self.FixingCommitClassifier = KubernetesFixingCommitClassifier

    def ignore_file(self, path_to_file: str, content: str = None):
        if not path_to_file:
            return True

        try:
            return not filters.is_kubernetes_file(path_to_file, content)
        except Exception:
            return True


# -----------------------------
# CLASSIFIER
# -----------------------------

class KubernetesFixingCommitClassifier(FixingCommitClassifier):
    # -----------------------------
    # LINGUISTIC DETECTION
    # -----------------------------

    def _has_kubernetes_bug_pattern(self, sentence: str) -> bool:
        if not sentence:
            return False

        sentence = sentence.lower()

        has_bug = any(k in sentence for k in KUBERNETES_DEFECT_KEYWORDS)
        has_context = any(k in sentence for k in KUBERNETES_CONTEXT_KEYWORDS)

        return has_bug and has_context

    def _has_issue_reference(self, sentence: str) -> bool:
        if not sentence:
            return False

        return bool(
            re.search(r"(fix(e[sd])?|close[sd]?|resolve[sd]?)\s+#\d+", sentence.lower())
        )

    # -----------------------------
    # YAML PARSING (ROBUSTO)
    # -----------------------------

    def _parse_yaml_docs(self, source):
        if not source or not isinstance(source, str):
            return []

        try:
            docs = list(yaml.safe_load_all(source))
            return [d for d in docs if isinstance(d, dict)]
        except Exception:
            return []

    # -----------------------------
    # EXTRACTORS
    # -----------------------------

    def _extract_kinds(self, parsed_docs) -> Set[str]:
        kinds = set()

        for doc in parsed_docs:
            try:
                kind = doc.get("kind")
                if isinstance(kind, str):
                    kinds.add(kind)
            except Exception:
                continue

        return kinds

    def _extract_images(self, parsed_docs) -> Set[str]:
        images = set()

        def safe_walk(obj, depth=0):
            if depth > 10:
                return

            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "image" and isinstance(v, str):
                        images.add(v)
                    else:
                        safe_walk(v, depth + 1)

            elif isinstance(obj, list):
                for item in obj:
                    safe_walk(item, depth + 1)

        for doc in parsed_docs:
            safe_walk(doc)

        return images

    def _is_valid_file(self, path, content):
        if not path:
            return False

        try:
            return filters.is_kubernetes_file(path, content)
        except Exception:
            return False

    # -----------------------------
    # SEMANTIC DETECTION
    # -----------------------------

    def is_service_changed(self) -> bool:

        for modified_file in self.commit.modified_files:

            if modified_file.change_type not in (
                    ModificationType.MODIFY,
                    ModificationType.ADD,
                    ModificationType.DELETE
            ):
                continue

            path = modified_file.new_path or modified_file.old_path

            if not self._is_valid_file(path, modified_file.source_code):
                continue

            before = self._parse_yaml_docs(modified_file.source_code_before)
            after = self._parse_yaml_docs(modified_file.source_code)

            if not before and not after:
                continue

            if self._extract_kinds(before) != self._extract_kinds(after):
                return True

        return False

    def is_dependency_changed(self) -> bool:

        for modified_file in self.commit.modified_files:

            if modified_file.change_type not in (
                    ModificationType.MODIFY,
                    ModificationType.ADD,
                    ModificationType.DELETE
            ):
                continue

            path = modified_file.new_path or modified_file.old_path

            if not self._is_valid_file(path, modified_file.source_code):
                continue

            before = self._parse_yaml_docs(modified_file.source_code_before)
            after = self._parse_yaml_docs(modified_file.source_code)

            if not before and not after:
                continue

            if self._extract_images(before) != self._extract_images(after):
                return True

        return False

    # -----------------------------
    # OVERRIDE BASE (SAFE)
    # -----------------------------

    def fixes_dependency(self):

        try:
            if self.is_dependency_changed():
                return True
        except Exception:
            pass

        for sentence in self.sentences:
            s = ' '.join(sentence)

            if self._has_issue_reference(s):
                return True

            if self._has_kubernetes_bug_pattern(s):
                return True

        return super().fixes_dependency()

    def fixes_service(self):

        try:
            if self.is_service_changed():
                return True
        except Exception:
            pass

        for sentence in self.sentences:
            s = ' '.join(sentence)

            if self._has_issue_reference(s):
                return True

            if self._has_kubernetes_bug_pattern(s):
                return True

        return super().fixes_service()