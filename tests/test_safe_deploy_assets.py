from pathlib import Path
import os
import stat
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SafeDeployAssetsTests(unittest.TestCase):
    def test_safe_deploy_script_exists_and_is_executable(self):
        script = ROOT / "scripts" / "deploy_gcp_vm.sh"
        self.assertTrue(script.exists())
        mode = script.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_safe_deploy_script_preserves_runtime_state(self):
        text = (ROOT / "scripts" / "deploy_gcp_vm.sh").read_text()
        self.assertIn('--exclude ".venv"', text)
        self.assertIn('install -m 0755', text)
        self.assertIn('vendorverdict-monitor.service', text)
        self.assertIn('vendorverdict-backup.service', text)
        self.assertIn('http://127.0.0.1:8080/health', text)

    def test_safe_deployment_docs_exist(self):
        doc = ROOT / "docs" / "SAFE_DEPLOYMENT.md"
        self.assertTrue(doc.exists())
        text = doc.read_text()
        self.assertIn('sudo scripts/deploy_gcp_vm.sh', text)
        self.assertIn('Never use plain rsync', text)


if __name__ == "__main__":
    unittest.main()
