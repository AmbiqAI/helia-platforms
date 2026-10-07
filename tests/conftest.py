import copy
from typing import Any

import pytest

RECORD = {
    "status": "datasheet",
    "source": ["doc:DS-TEST@1.0:p1"],
    "verified_on": "2026-10-05",
    "verified_by": "tester",
}

# A small, complete document with illustrative values (no real part is described).
BASE_DOCUMENT: dict[str, Any] = {
    "schema_version": 1,
    "cores": {
        "cortex-m55": {"arch": "armv8.1-m", "pmu": "armv8m", "has_dsp_extension": True},
        "cortex-m4": {"arch": "armv7e-m", "pmu": "dwt", "has_dsp_extension": True},
    },
    "socs": {
        "soc_a": {
            "series": "test",
            "provenance": RECORD,
            "cores": [
                {
                    "id": "cm55_0",
                    "role": "application",
                    "core": "cortex-m55",
                    "clock_domain": "cpu",
                    "options": {"fpu": "fpv5-sp-d16", "mve": "fp"},
                    "programmable_by": "customer",
                }
            ],
            "npus": [
                {
                    "id": "npu_0",
                    "npu": {
                        "vendor": "arm",
                        "family": "ethos-u",
                        "model": "u85",
                        "macs_per_cycle": 256,
                    },
                    "driven_by": "cm55_0",
                    "clock_domain": "npu",
                }
            ],
            "memories": {
                "tcm": {
                    "technology": "sram",
                    "attachment": "tcm",
                    "base": 0x20000000,
                    "size": "512K",
                },
                "ssram": {
                    "technology": "sram",
                    "attachment": "system",
                    "base": 0x20080000,
                    "size": "3M",
                },
                "nvm": {
                    "technology": "mram",
                    "attachment": "system",
                    "base": 0x00400000,
                    "size": "4M",
                },
            },
            "peripherals": ["mspi0", "iom0", "iom1", "iom2"],
            "access": [
                {"master": "npu_0", "target": "ssram", "access": "direct", "port": 0},
                {"master": "npu_0", "target": "tcm", "access": "direct", "guidance": "discouraged"},
            ],
            "default_access": {"master": "cm55_0", "access": "direct", "scope": "on_die"},
            "clock_domains": {
                "cpu": {"lp": {"mhz": 96}, "hp": {"mhz": 192}},
                "npu": {"lp": {"mhz": 96}},
            },
            "operating_points": {
                "lp": {"domains": {"cpu": "lp", "npu": "lp"}},
                "hp": {"cpu_mhz": 192, "npu_mhz": 192},
            },
            "default_operating_point": "lp",
            "boot_configs": {
                "sbl": {
                    "reserved": {"sbl": {"region": "nvm", "offset": 0, "size": "64K"}},
                    "app_start": {"region": "nvm", "offset": "64K"},
                    "requires": "sbl",
                },
                "nbl": {
                    "reserved": {},
                    "app_start": {"region": "nvm", "offset": 0},
                    "requires": "none",
                },
            },
            "default_boot": "sbl",
        }
    },
    "parts": {"PART-A": {"soc": "soc_a", "silicon_revision": "B0"}},
    "memory_devices": {"psram_8m": {"technology": "psram", "capacity": "8M"}},
    "boards": {
        "board_a": {
            "category": "evaluation",
            "part": "PART-A",
            "interfaces": {
                "mspi0": {
                    "controller": "mspi0",
                    "aperture_base": 0x60000000,
                    "aperture_max": "256M",
                }
            },
            "population": {"mspi0": "psram_8m"},
            "provisioning": "sbl",
        }
    },
}


@pytest.fixture
def document() -> dict[str, Any]:
    """A fresh copy of the base document, safe to mutate."""
    return copy.deepcopy(BASE_DOCUMENT)
