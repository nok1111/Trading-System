from app.utils.security import mask_secret


class TestSecurityHelpers:
    def test_mask_secret_hides_middle(self) -> None:
        assert mask_secret("abcdefgh12345678", visible=4) == "abcd***5678"

    def test_mask_short_secret(self) -> None:
        assert mask_secret("abcd", visible=4) == "****"

    def test_mask_none_or_empty(self) -> None:
        assert mask_secret(None) == "not_set"
        assert mask_secret("") == "not_set"
