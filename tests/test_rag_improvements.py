"""
Unit tests for RAG improvements: query expansion, ambiguity detection, and field-weighted scoring.
Tests for the new functions added in the RAG enhancement initiative.
"""

import pytest
from app.services.rag.chains import (
    query_specificity_score,
    expand_ambiguous_query,
    _normalize_text,
    _tokenize,
    AMBIGUOUS_TERM_MAPPINGS,
)
from app.services.search_service import _calculate_field_weight
from app.models.sanction import Sanction


class TestQuerySpecificityScore:
    """Tests for query_specificity_score function."""
    
    def test_very_generic_query_single_word(self):
        """Very generic single-word query should have low score."""
        score = query_specificity_score("TRADING")
        assert score < 0.4, f"Expected score < 0.4 for 'TRADING', got {score}"
    
    def test_generic_query_with_expansion(self):
        """Generic query with few tokens should score low."""
        score = query_specificity_score("GROUP")
        assert score < 0.4, f"Expected score < 0.4 for 'GROUP', got {score}"
    
    def test_specific_query_with_rfc(self):
        """Query with RFC identifier should have high score."""
        score = query_specificity_score("Juan Perez RFC AAAJ830204PA9")
        assert score > 0.5, f"Expected score > 0.5 for RFC query, got {score}"
    
    def test_specific_query_with_multiple_tokens(self):
        """Query with multiple specific tokens should have high score."""
        score = query_specificity_score("Juan Carlos Araiza Arambula SAT")
        assert score > 0.4, f"Expected score > 0.4 for specific query, got {score}"
    
    def test_medium_specificity_query(self):
        """Query with some specificity should score in middle range."""
        score = query_specificity_score("TRADING COMPANY Mexico")
        assert 0.2 < score < 0.8, f"Expected score in range (0.2, 0.8), got {score}"
    
    def test_score_bounds_are_valid(self):
        """Score should always be between 0 and 1."""
        test_queries = [
            "TRADING",
            "TRADING COMPANY",
            "Juan Perez RFC AAAJ830204PA9",
            "A very long query with many tokens and identifiers RFC AAAJ830204PA9 in SAT",
        ]
        for query in test_queries:
            score = query_specificity_score(query)
            assert 0 <= score <= 1, f"Score out of bounds for '{query}': {score}"


class TestExpandAmbiguousQuery:
    """Tests for expand_ambiguous_query function."""
    
    def test_trading_expansion(self):
        """TRADING should expand to commerce-related terms."""
        expansions = expand_ambiguous_query("TRADING")
        assert len(expansions) > 0, "No expansions returned for 'TRADING'"
        # Should contain at least one commerce-related term
        expected_terms = {"commercial", "import", "export", "goods", "commerce", "business", "comercio"}
        actual_set = set(expansions)
        assert actual_set & expected_terms, f"No expected terms in {actual_set}"
    
    def test_group_expansion(self):
        """GROUP should expand to organizational terms."""
        expansions = expand_ambiguous_query("GROUP")
        assert len(expansions) > 0, "No expansions returned for 'GROUP'"
        expected_terms = {"holding", "subsidiary", "parent", "cluster"}
        actual_set = set(expansions)
        assert actual_set & expected_terms, f"No expected terms in {actual_set}"
    
    def test_company_expansion(self):
        """COMPANY should expand to entity-related terms."""
        expansions = expand_ambiguous_query("COMPANY")
        assert len(expansions) > 0, "No expansions returned for 'COMPANY'"
        expected_terms = {"entity", "organization", "enterprise", "sociedad", "empresa"}
        actual_set = set(expansions)
        assert actual_set & expected_terms, f"No expected terms in {actual_set}"
    
    def test_no_expansion_for_specific_query(self):
        """Specific query with no ambiguous terms should return empty expansions."""
        expansions = expand_ambiguous_query("Juan Perez RFC AAAJ830204PA9")
        assert len(expansions) == 0, f"Expected no expansions for specific query, got {expansions}"
    
    def test_multiple_ambiguous_terms(self):
        """Query with multiple ambiguous terms should expand each."""
        expansions = expand_ambiguous_query("TRADING GROUP")
        # Should have expansions for both TRADING and GROUP
        assert len(expansions) > 0, "No expansions returned"
        # Verify we have variety
        trading_expansions = set(AMBIGUOUS_TERM_MAPPINGS.get("trading", []))
        group_expansions = set(AMBIGUOUS_TERM_MAPPINGS.get("group", []))
        expected = trading_expansions | group_expansions
        actual = set(expansions)
        assert actual == expected, f"Mismatch: expected {expected}, got {actual}"


class TestFieldWeightCalculation:
    """Tests for _calculate_field_weight function."""
    
    def test_entity_name_match_highest_weight(self):
        """Match in entity_name should give highest weight (1.0)."""
        sanction = Sanction(
            entity_name="TRADING COMPANY S.A.",
            aliases=None,
            designation=None,
            remarks=None,
        )
        score = _calculate_field_weight("trading", sanction)
        assert score == 1.0, f"Expected 1.0 for entity_name match, got {score}"
    
    def test_aliases_match_high_weight(self):
        """Match in aliases should give 0.9 weight."""
        sanction = Sanction(
            entity_name="Company Name",
            aliases=["TRADING ALIAS", "Another Name"],
            designation=None,
            remarks=None,
        )
        score = _calculate_field_weight("trading", sanction)
        assert score == 0.9, f"Expected 0.9 for aliases match, got {score}"
    
    def test_designation_match_medium_weight(self):
        """Match in designation should give 0.7 weight."""
        sanction = Sanction(
            entity_name="Company Name",
            aliases=None,
            designation=["Commercial Trading Entity"],
            remarks=None,
        )
        score = _calculate_field_weight("trading", sanction)
        assert score == 0.7, f"Expected 0.7 for designation match, got {score}"
    
    def test_remarks_match_lower_weight(self):
        """Match in remarks should give 0.5 weight."""
        sanction = Sanction(
            entity_name="Company Name",
            aliases=None,
            designation=None,
            remarks="This entity is involved in trading activities",
        )
        score = _calculate_field_weight("trading", sanction)
        assert score == 0.5, f"Expected 0.5 for remarks match, got {score}"
    
    def test_no_match_default_weight(self):
        """No match should return default 0.8 score."""
        sanction = Sanction(
            entity_name="Unrelated Company",
            aliases=None,
            designation=None,
            remarks=None,
        )
        score = _calculate_field_weight("trading", sanction)
        assert score == 0.8, f"Expected 0.8 as default, got {score}"
    
    def test_highest_weight_wins_multiple_matches(self):
        """When multiple fields match, highest weight should win."""
        sanction = Sanction(
            entity_name="TRADING COMPANY",
            aliases=["Trade Alias"],
            designation=["Trading Entity"],
            remarks="Also mentions trading here",
        )
        score = _calculate_field_weight("trading", sanction)
        # Should return 1.0 because entity_name has highest weight
        assert score == 1.0, f"Expected 1.0 for highest weight, got {score}"


class TestAmbiguousTermMappings:
    """Tests to verify AMBIGUOUS_TERM_MAPPINGS dictionary."""
    
    def test_mappings_exist(self):
        """All key ambiguous terms should have mappings."""
        required_terms = ["trading", "group", "company", "finance", "import", "export"]
        for term in required_terms:
            assert term in AMBIGUOUS_TERM_MAPPINGS, f"Missing mapping for '{term}'"
            assert len(AMBIGUOUS_TERM_MAPPINGS[term]) > 0, f"Empty mapping for '{term}'"
    
    def test_mappings_have_reasonable_values(self):
        """Mappings should contain reasonable expansion terms."""
        for term, expansions in AMBIGUOUS_TERM_MAPPINGS.items():
            for exp in expansions:
                assert isinstance(exp, str), f"Non-string expansion: {exp} for term {term}"
                assert len(exp) > 1, f"Too short expansion: {exp} for term {term}"


class TestIntegrationAmbiguityDetection:
    """Integration tests for ambiguity detection workflow."""
    
    def test_trading_query_is_ambiguous(self):
        """Query 'TRADING' should be detected as ambiguous."""
        score = query_specificity_score("TRADING")
        is_ambiguous = score < 0.4
        assert is_ambiguous, f"'TRADING' should be ambiguous, specificity_score={score}"
    
    def test_expanded_search_candidates_include_expansions(self):
        """Expanded search should include expansion terms."""
        from app.services.rag.chains import _build_search_candidates
        candidates = _build_search_candidates("TRADING")
        # Should have more than just "TRADING"
        assert len(candidates) > 1, f"Expected multiple candidates, got {candidates}"
        # Should include some expanded terms
        expanded_terms = set(AMBIGUOUS_TERM_MAPPINGS.get("trading", []))
        candidates_set = set(candidates)
        has_expansions = bool(candidates_set & expanded_terms)
        assert has_expansions, f"No expansions in candidates {candidates}"
    
    def test_specific_query_not_ambiguous(self):
        """Query with RFC should not be ambiguous."""
        score = query_specificity_score("Juan Perez RFC AAAJ830204PA9")
        is_ambiguous = score < 0.4
        assert not is_ambiguous, f"RFC query should not be ambiguous, specificity_score={score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
