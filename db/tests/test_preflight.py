from golfdb.catalog import CourseCatalog, load_catalog
from golfdb.preflight import production_errors


def test_development_catalog_is_not_production_ready():
    errors = production_errors(load_catalog())
    assert any("stub-north" in error for error in errors)
    assert not any("club-mandalay" in error for error in errors)


def test_empty_production_catalog_is_rejected():
    assert production_errors(CourseCatalog(courses=[]))


def test_miclub_requires_matching_host_and_supported_fee_groups():
    course = load_catalog().courses[0].model_copy(update={
        "params": {"base_url": "https://wrong.example", "fee_groups": [{"id": "bad", "holes": 36}]}
    })
    errors = production_errors(CourseCatalog(courses=[course]))
    assert any("booking host" in error for error in errors)
    assert any("booking_resource_id" in error for error in errors)
    assert any("fee group" in error for error in errors)
