from app.providers.models import ProviderCostClass, ProviderCreate, ProviderKind


def test_canonical_cost_classes_have_no_ambiguous_free_value() -> None:
    assert {item.value for item in ProviderCostClass} == {
        "LOCAL_FREE",
        "FREE_TIER",
        "PAID",
        "UNKNOWN",
    }
    assert "FREE" not in {item.value for item in ProviderCostClass}


def test_cloud_provider_defaults_to_unknown_not_free() -> None:
    provider = ProviderCreate(name="Cloud", kind=ProviderKind.OPENAI)
    assert provider.cost_class is ProviderCostClass.UNKNOWN
    assert provider.enabled is False


def test_local_and_free_tier_labels_are_distinct() -> None:
    assert ProviderCostClass.LOCAL_FREE.value != ProviderCostClass.FREE_TIER.value
