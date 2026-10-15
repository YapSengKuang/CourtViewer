"""Offline validation of a launch catalog; does not claim live source access."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from golfdb.catalog import CourseCatalog, load_catalog


def production_errors(catalog: CourseCatalog) -> list[str]:
    errors: list[str] = []
    if not catalog.courses:
        errors.append("production catalog must contain at least one course")
    for course in catalog.courses:
        prefix = f"{course.id}: "
        if course.id.startswith("stub-") or course.platform != "miclub":
            errors.append(prefix + "no verified production adapter (only miclub is currently implemented)")
        url = urlsplit(course.booking_url or "")
        if url.scheme != "https" or not url.hostname or url.hostname.endswith(".invalid"):
            errors.append(prefix + "a real HTTPS booking URL is required")
        if course.platform == "miclub":
            base = urlsplit(str(course.params.get("base_url", "")))
            if base.scheme != "https" or base.hostname != url.hostname:
                errors.append(prefix + "base_url must use HTTPS and match the booking host")
            if not str(course.params.get("booking_resource_id", "")).isdigit():
                errors.append(prefix + "numeric booking_resource_id is required")
            groups = course.params.get("fee_groups")
            if not isinstance(groups, list) or not groups:
                errors.append(prefix + "fee_groups must be a nonempty list")
                continue
            for group in groups:
                if (not isinstance(group, dict)
                        or not str(group.get("id", "")).isdigit()
                        or group.get("holes") not in course.holes_options):
                    errors.append(prefix + "each fee group needs a numeric id and supported holes")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    errors = production_errors(load_catalog(args.catalog))
    if errors:
        parser.exit(1, "Catalog preflight failed:\n" + "\n".join(errors) + "\n")
    print("Catalog configuration valid. Live access, pricing and capacity still need verification.")


if __name__ == "__main__":
    main()
