"""Unit tests for extraction prompts and schema definitions."""
import pytest
from app.services.extraction.prompts import (
    EXTRACTION_PROMPTS,
    build_prompt,
    get_primary_field,
    get_date_field,
    get_searchable_fields,
)


# ---------------------------------------------------------------------------
# All document types covered
# ---------------------------------------------------------------------------
ALL_DOC_TYPES = [
    "CUSTOMER_PO",
    "COMPANY_PO",
    "VENDOR_DC",
    "VENDOR_INVOICE",
    "COMPANY_DC",
    "COMPANY_INVOICE",
]


class TestExtractionPromptRegistry:
    """Every declared document type must have a prompt config."""

    def test_all_doc_types_have_prompts(self):
        for dt in ALL_DOC_TYPES:
            assert dt in EXTRACTION_PROMPTS, f"Missing prompt config for {dt}"

    def test_each_prompt_has_instruction_and_schema(self):
        for dt, cfg in EXTRACTION_PROMPTS.items():
            assert "instruction" in cfg, f"{dt}: missing 'instruction'"
            assert "schema" in cfg, f"{dt}: missing 'schema'"
            assert isinstance(cfg["schema"], dict)
            assert len(cfg["schema"]) > 0, f"{dt}: schema is empty"


# ---------------------------------------------------------------------------
# CUSTOMER_PO schema
# ---------------------------------------------------------------------------
class TestCustomerPOSchema:
    @property
    def schema(self):
        return EXTRACTION_PROMPTS["CUSTOMER_PO"]["schema"]

    def test_has_po_number(self):
        assert "po_number" in self.schema

    def test_has_po_date(self):
        assert "po_date" in self.schema

    def test_has_bsif_name(self):
        assert "bsif_name" in self.schema


# ---------------------------------------------------------------------------
# COMPANY_PO schema
# ---------------------------------------------------------------------------
class TestCompanyPOSchema:
    @property
    def schema(self):
        return EXTRACTION_PROMPTS["COMPANY_PO"]["schema"]

    def test_has_purchase_bill_no(self):
        assert "purchase_bill_no" in self.schema

    def test_has_po_number(self):
        assert "po_number" in self.schema

    def test_has_bill_no(self):
        assert "bill_no" in self.schema

    def test_no_extra_fields(self):
        assert set(self.schema.keys()) == {"purchase_bill_no", "po_number", "bill_no"}


# ---------------------------------------------------------------------------
# COMPANY_DC schema
# ---------------------------------------------------------------------------
class TestCompanyDCSchema:
    @property
    def schema(self):
        return EXTRACTION_PROMPTS["COMPANY_DC"]["schema"]

    def test_has_dc_number(self):
        assert "dc_number" in self.schema

    def test_has_po_reference(self):
        assert "po_reference" in self.schema

    def test_has_sales_order_no(self):
        assert "sales_order_no" in self.schema

    def test_has_dispatch_to(self):
        assert "dispatch_to" in self.schema

    def test_instruction_mentions_non_returnable(self):
        instr = EXTRACTION_PROMPTS["COMPANY_DC"]["instruction"]
        assert "NON RETURNABLE DELIVERY CHALLAN" in instr

    def test_instruction_warns_about_reference_field(self):
        instr = EXTRACTION_PROMPTS["COMPANY_DC"]["instruction"]
        assert "Customer Order No." in instr
        assert "person name" in instr.lower()


# ---------------------------------------------------------------------------
# COMPANY_INVOICE schema
# ---------------------------------------------------------------------------
class TestCompanyInvoiceSchema:
    @property
    def schema(self):
        return EXTRACTION_PROMPTS["COMPANY_INVOICE"]["schema"]

    def test_has_invoice_number(self):
        assert "invoice_number" in self.schema

    def test_has_po_reference(self):
        assert "po_reference" in self.schema

    def test_has_so_number(self):
        assert "so_number" in self.schema

    def test_has_customer_name(self):
        assert "customer_name" in self.schema

    def test_has_total_amount(self):
        assert "total_amount" in self.schema

    def test_instruction_mentions_customer_order_no(self):
        instr = EXTRACTION_PROMPTS["COMPANY_INVOICE"]["instruction"]
        assert "Customer Order No." in instr

    def test_instruction_mentions_so_no(self):
        instr = EXTRACTION_PROMPTS["COMPANY_INVOICE"]["instruction"]
        assert "SO No." in instr


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------
class TestBuildPrompt:
    def test_returns_string_for_all_types(self):
        for dt in ALL_DOC_TYPES:
            prompt = build_prompt(dt)
            assert isinstance(prompt, str)
            assert len(prompt) > 100

    def test_includes_system_prompt_rules(self):
        prompt = build_prompt("COMPANY_DC")
        assert "RULES" in prompt
        assert "NEVER use commas" in prompt

    def test_includes_all_schema_fields(self):
        prompt = build_prompt("COMPANY_DC")
        for field in EXTRACTION_PROMPTS["COMPANY_DC"]["schema"]:
            assert field in prompt, f"Field '{field}' missing from built prompt"

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown document type"):
            build_prompt("UNKNOWN_TYPE")


# ---------------------------------------------------------------------------
# get_primary_field / get_date_field
# ---------------------------------------------------------------------------
class TestPrimaryAndDateFields:
    @pytest.mark.parametrize(
        "doc_type,expected",
        [
            ("CUSTOMER_PO", "po_number"),
            ("COMPANY_PO", "purchase_bill_no"),
            ("VENDOR_DC", "dc_number"),
            ("VENDOR_INVOICE", "invoice_number"),
            ("COMPANY_DC", "dc_number"),
            ("COMPANY_INVOICE", "invoice_number"),
        ],
    )
    def test_primary_field(self, doc_type, expected):
        assert get_primary_field(doc_type) == expected

    @pytest.mark.parametrize(
        "doc_type,expected",
        [
            ("CUSTOMER_PO", "po_date"),
            ("COMPANY_PO", ""),
            ("VENDOR_DC", "dc_date"),
            ("VENDOR_INVOICE", ""),
            ("COMPANY_DC", ""),
            ("COMPANY_INVOICE", ""),
        ],
    )
    def test_date_field(self, doc_type, expected):
        assert get_date_field(doc_type) == expected

    def test_unknown_type_returns_empty(self):
        assert get_primary_field("NOPE") == ""
        assert get_date_field("NOPE") == ""


# ---------------------------------------------------------------------------
# get_searchable_fields
# ---------------------------------------------------------------------------
class TestSearchableFields:
    def test_all_doc_types_have_searchable_fields(self):
        for dt in ALL_DOC_TYPES:
            fields = get_searchable_fields(dt)
            assert isinstance(fields, list)
            assert len(fields) > 0, f"No searchable fields for {dt}"

    def test_company_dc_includes_sales_order_no(self):
        fields = get_searchable_fields("COMPANY_DC")
        ref_types = [rt for rt, _ in fields]
        assert "sales_order_no" in ref_types

    def test_company_dc_includes_dc_number(self):
        fields = get_searchable_fields("COMPANY_DC")
        ref_types = [rt for rt, _ in fields]
        assert "dc_number" in ref_types

    def test_company_dc_includes_po_reference(self):
        fields = get_searchable_fields("COMPANY_DC")
        ref_types = [rt for rt, _ in fields]
        assert "po_reference" in ref_types

    def test_company_invoice_includes_so_number(self):
        fields = get_searchable_fields("COMPANY_INVOICE")
        ref_types = [rt for rt, _ in fields]
        assert "so_number" in ref_types

    def test_company_po_includes_bill_no(self):
        fields = get_searchable_fields("COMPANY_PO")
        ref_types = [rt for rt, _ in fields]
        assert "bill_no" in ref_types

    def test_company_po_includes_purchase_bill_no(self):
        fields = get_searchable_fields("COMPANY_PO")
        ref_types = [rt for rt, _ in fields]
        assert "purchase_bill_no" in ref_types

    def test_unknown_type_returns_empty_list(self):
        assert get_searchable_fields("NOPE") == []

    def test_searchable_fields_match_schema_keys(self):
        """Every searchable field must exist in the schema."""
        for dt in ALL_DOC_TYPES:
            schema_keys = set(EXTRACTION_PROMPTS[dt]["schema"].keys())
            for _, field_name in get_searchable_fields(dt):
                assert field_name in schema_keys, (
                    f"Searchable field '{field_name}' for {dt} not in schema"
                )
