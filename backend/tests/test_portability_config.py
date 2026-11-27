import unittest

from app.config import get_cors_origins, resolve_project_path, PROJECT_ROOT


class PortabilityConfigurationTests(unittest.TestCase):
    def test_relative_paths_resolve_from_repository_root(self):
        path = resolve_project_path("custom-data/images", "fallback")
        self.assertEqual(path, (PROJECT_ROOT / "custom-data" / "images").resolve())

    def test_empty_configured_path_uses_default(self):
        path = resolve_project_path("", "backend/uploads")
        self.assertEqual(path, (PROJECT_ROOT / "backend" / "uploads").resolve())

    def test_absolute_paths_are_preserved(self):
        absolute = (PROJECT_ROOT / "external-assets").resolve()
        self.assertEqual(resolve_project_path(absolute, "fallback"), absolute)

    def test_cors_origins_are_trimmed_deduplicated_and_slash_normalized(self):
        origins = get_cors_origins({
            "CORS_ORIGINS": " https://app.example.com/ , https://app.example.com, http://localhost:5173 ",
        })
        self.assertEqual(origins, ["https://app.example.com", "http://localhost:5173"])

    def test_credentialed_cors_rejects_wildcard(self):
        with self.assertRaisesRegex(RuntimeError, "cannot contain"):
            get_cors_origins({"CORS_ORIGINS": "https://app.example.com,*"})

    def test_frontend_base_url_is_added_to_default_development_origins(self):
        origins = get_cors_origins({"FRONTEND_BASE_URL": "https://app.example.com/reset"})
        self.assertEqual(origins[0], "https://app.example.com")
        self.assertIn("http://localhost:5173", origins)


if __name__ == "__main__":
    unittest.main()
