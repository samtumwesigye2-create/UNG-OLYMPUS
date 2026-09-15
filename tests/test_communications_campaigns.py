"""TDD acceptance tests for the OLYMPUS communications campaign lifecycle."""

import pytest


def test_create_campaign_starts_as_draft(tmp_path):
    from communications.db import CommunicationsDB

    db = CommunicationsDB(str(tmp_path / "communications.db"))
    campaign = db.create_campaign(
        name="National Service Advisory",
        created_by="commander-1",
        scope="national",
    )

    assert campaign["name"] == "National Service Advisory"
    assert campaign["scope"] == "national"
    assert campaign["status"] == "draft"
    assert campaign["created_by"] == "commander-1"


def test_campaign_lifecycle_rejects_invalid_transition(tmp_path):
    from communications.db import CommunicationsDB, InvalidCampaignTransition

    db = CommunicationsDB(str(tmp_path / "communications.db"))
    campaign = db.create_campaign(
        name="Regional Advisory",
        created_by="commander-1",
        scope="regional",
    )

    with pytest.raises(InvalidCampaignTransition):
        db.transition_campaign(campaign["id"], "sending")


def test_nationwide_campaign_requires_two_distinct_approvers(tmp_path):
    from communications.db import CommunicationsDB, ApprovalRequired

    db = CommunicationsDB(str(tmp_path / "communications.db"))
    campaign = db.create_campaign(
        name="National Emergency Notice",
        created_by="commander-1",
        scope="national",
    )
    db.transition_campaign(campaign["id"], "audience_validation")
    db.transition_campaign(campaign["id"], "translation")
    db.transition_campaign(campaign["id"], "approval")

    db.approve_campaign(campaign["id"], "approver-1")
    db.approve_campaign(campaign["id"], "approver-1")

    with pytest.raises(ApprovalRequired):
        db.transition_campaign(campaign["id"], "ready")

    db.approve_campaign(campaign["id"], "approver-2")
    ready = db.transition_campaign(campaign["id"], "ready")
    assert ready["status"] == "ready"
