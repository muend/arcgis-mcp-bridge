"""Tests/test_registry.py - Declarative tool registry schema integrity and generator tests."""

import types

# Python dekoratörlerinin yan etkilerini tetiklemek ve diskteki tüm
# araç tanımlarını hafızaya yüklemek için araç paketini import ediyoruz.
# DİKKAT: Bu import bir yan-etki tetikleyicisidir (registry'yi doldurur);
# linter tarafından asla silinmemelidir.
import arcgis_mcp.tools  # noqa: F401
from arcgis_mcp.registry import all_specs, count


def test_registry_discovery_and_type() -> None:
    """Ensures the central registry initializes as a valid stream or collection."""
    specs = all_specs()

    # Doğrulama: Yapı ya bir sözlüktür ya da bellek dostu bir Generator (Üreteç) nesnesidir
    assert isinstance(specs, (dict, types.GeneratorType)) or hasattr(
        specs, "__iter__"
    ), "Registry must be a dict or a memory-efficient generator/iterable"

    # Tetikleme sonrası araç sayısının başarıyla doldurulduğunu doğrula
    assert count() > 0, (
        "Registry internal tool counter should not be zero after module discovery"
    )


def test_registry_metadata_and_contract_integrity() -> None:
    """Validates that every single registered tool obeys strict Pydantic metadata bounds."""
    specs = all_specs()

    # Jeneratör akışını test içinde güvenle tüketmek ve normalize etmek için
    # dinamik bir sözlük haritası inşa ediyoruz
    specs_dict = {}
    for item in specs:
        if isinstance(item, tuple) and len(item) == 2:
            name, spec = item
            specs_dict[name] = spec
        else:
            # Eğer doğrudan nesne olarak yield ediliyorsa adını nesneden oku
            specs_dict[item.name] = item

    # Normalize edilmiş sözlük uzunluğu ile merkezi sayacı eşleştir
    assert len(specs_dict) == count(), (
        "Registry internal counter drift detected during stream consumption"
    )
    assert len(specs_dict) > 0, "No tools discovered in the validation dictionary"

    # ToolSpec stores its Pydantic contract under 'input_model' (canonical);
    # legacy candidates kept for forward-compat introspection resilience.
    possible_schema_fields = [
        "input_model",
        "input_schema",
        "schema",
        "parameters",
        "args",
        "args_schema",
        "input_contract",
    ]

    from arcgis_mcp.contracts.base import ToolInput

    for tool_name, spec in specs_dict.items():
        # 1. Sözdizimsel İsim Doğrulaması
        assert spec.name == tool_name, (
            f"Naming collision or drift in tool specification: {tool_name}"
        )

        # 2. Semantik Bağlam Kalitesi (LLM Açıklama Uzunluğu)
        assert spec.description is not None, (
            f"Tool '{tool_name}' is missing a definition string"
        )
        assert len(spec.description) >= 15, (
            f"Description for '{tool_name}' is too short for semantic LLM routing"
        )

        # 3. Dinamik Girdi Kontrat Doğrulaması (Self-Healing Introspection)
        found_schema_attr = next(
            (
                attr
                for attr in possible_schema_fields
                if getattr(spec, attr, None) is not None
            ),
            None,
        )
        assert found_schema_attr is not None, (
            f"Tool '{tool_name}' has no identifiable schema attribute. "
            f"Available object attributes: {[a for a in dir(spec) if not a.startswith('_')]}"
        )

        # 4. Kontratın gerçek bir ToolInput Pydantic modeli olduğunu kanıtla
        model = getattr(spec, found_schema_attr)
        assert isinstance(model, type) and issubclass(model, ToolInput), (
            f"Schema for '{tool_name}' is not a ToolInput subclass: {model!r}"
        )

        # 5. Güvenlik tabanı: path_fields beyanları gerçek model alanlarına
        #    işaret etmeli ve geçerli rollerle sınırlı olmalı (hayalet alan yok)
        for field, role in model.path_fields.items():
            assert field in model.model_fields, (
                f"'{tool_name}': path_fields declares ghost field '{field}'"
            )
            assert role in ("read", "write", "read_list"), (
                f"'{tool_name}': invalid path role '{role}' on '{field}'"
            )

        # 6. Yıkıcı araçlar mutlaka 'confirm' kapısı taşımalı
        if spec.destructive:
            assert "confirm" in model.model_fields, (
                f"Destructive tool '{tool_name}' lacks a confirm gate"
            )
