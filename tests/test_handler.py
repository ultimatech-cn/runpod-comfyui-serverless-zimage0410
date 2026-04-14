import sys
import types
import unittest
from unittest import mock


runpod_module = types.ModuleType("runpod")
serverless_module = types.ModuleType("runpod.serverless")
utils_module = types.ModuleType("runpod.serverless.utils")
rp_upload_module = types.ModuleType("runpod.serverless.utils.rp_upload")


def _fake_upload_image(*args, **kwargs):
    return "stub-upload"


rp_upload_module.upload_image = _fake_upload_image
utils_module.rp_upload = rp_upload_module
serverless_module.utils = utils_module
runpod_module.serverless = serverless_module

requests_module = types.ModuleType("requests")


class _FakeRequestException(Exception):
    pass


requests_module.RequestException = _FakeRequestException

websocket_module = types.ModuleType("websocket")

sys.modules.setdefault("runpod", runpod_module)
sys.modules.setdefault("runpod.serverless", serverless_module)
sys.modules.setdefault("runpod.serverless.utils", utils_module)
sys.modules.setdefault("runpod.serverless.utils.rp_upload", rp_upload_module)
sys.modules.setdefault("requests", requests_module)
sys.modules.setdefault("websocket", websocket_module)

import handler


class TestHandlerInputValidation(unittest.TestCase):
    def test_workflow_only_is_valid(self):
        validated, error = handler.validate_input({"workflow": {"foo": "bar"}})
        self.assertIsNone(error)
        self.assertEqual(validated["workflow"], {"foo": "bar"})
        self.assertIsNone(validated["images"])

    def test_missing_workflow_is_invalid(self):
        _, error = handler.validate_input({"images": []})
        self.assertEqual(error, "Missing 'workflow' parameter")

    def test_invalid_images_shape_is_rejected(self):
        _, error = handler.validate_input(
            {"workflow": {"foo": "bar"}, "images": [{"name": "x"}]}
        )
        self.assertEqual(
            error, "'images' must be a list of objects with 'name' and 'image' keys"
        )


class TestNormalizeWorkflowPaths(unittest.TestCase):
    def test_backslashes_are_normalized_for_likely_paths(self):
        workflow = {
            "1": {
                "inputs": {
                    "lora_name": "WAN\\demo.safetensors",
                    "note": "leave me alone"
                }
            }
        }

        normalized = handler.normalize_workflow_paths(workflow)
        self.assertEqual(
            normalized["1"]["inputs"]["lora_name"],
            "WAN/demo.safetensors",
        )
        self.assertEqual(normalized["1"]["inputs"]["note"], "leave me alone")


class TestDetectModelsRoot(unittest.TestCase):
    def test_override_path_is_used_when_present(self):
        with mock.patch.dict(handler.os.environ, {"RUNPOD_MODELS_PATH": "/custom/models"}, clear=False):
            with mock.patch.object(handler.os.path, "isdir", side_effect=lambda path: path == "/custom/models"):
                self.assertEqual(handler.detect_models_root(), "/custom/models")

    def test_workspace_models_path_is_detected(self):
        def fake_isdir(path):
            return path in {"/workspace/models"}

        with mock.patch.dict(handler.os.environ, {}, clear=True):
            with mock.patch.object(handler.os.path, "isdir", side_effect=fake_isdir):
                with mock.patch.object(handler.os, "walk", return_value=[]):
                    self.assertEqual(handler.detect_models_root(), "/workspace/models")


if __name__ == "__main__":
    unittest.main()
