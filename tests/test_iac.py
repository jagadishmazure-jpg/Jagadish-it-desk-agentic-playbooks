"""Infrastructure is written, not run: Terraform and Bicep stay in step, and the deploy path is gated."""

import re

from conftest import ROOT

TF = (ROOT / "infra/terraform/main.tf").read_text()
BICEP = (ROOT / "infra/bicep/main.bicep").read_text()
DEPLOY = (ROOT / ".github/workflows/deploy.yml").read_text()

TF_TO_ARM = {
    "azurerm_log_analytics_workspace": "Microsoft.OperationalInsights/workspaces",
    "azurerm_application_insights": "Microsoft.Insights/components",
    "azurerm_storage_account": "Microsoft.Storage/storageAccounts",
    "azurerm_key_vault": "Microsoft.KeyVault/vaults",
    "azurerm_monitor_diagnostic_setting": "Microsoft.Insights/diagnosticSettings",
    "azurerm_role_assignment": "Microsoft.Authorization/roleAssignments",
}


def tf_types():
    out = [TF_TO_ARM[k] for k in re.findall(r'^resource "(\w+)"', TF, re.M) if k in TF_TO_ARM]
    return sorted(out + re.findall(r'type\s*=\s*"([\w./]+)@', TF))


def test_terraform_and_bicep_create_the_same_resources():
    assert tf_types() == sorted(re.findall(r"^resource \w+ '([\w./]+)@", BICEP, re.M))


def test_endpoint_uses_entra_tokens_and_storage_is_entra_only():
    assert 'authMode            = "AADToken"' in TF and "authMode: 'AADToken'" in BICEP
    assert "shared_access_key_enabled       = false" in TF and "allowSharedKeyAccess: false" in BICEP


def test_endpoint_can_only_read_connector_secrets():
    assert 'role_definition_name = "Key Vault Secrets User"' in TF
    assert "4633458b-17de-408a-b874-0445c86b69e6" in BICEP  # built-in Key Vault Secrets User role id
    assert TF.count('resource "azurerm_role_assignment"') == 1


def test_deploy_workflow_is_manual_gated_and_oidc():
    assert re.search(r"^on:\n  workflow_dispatch:", DEPLOY, re.M) and "push:" not in DEPLOY
    jobs = re.findall(r"^  ([\w-]+):\n", DEPLOY.split("\njobs:\n", 1)[1], re.M)
    for job in jobs:
        if job != "preflight":
            block = DEPLOY.split(f"\n  {job}:\n", 1)[1]
            assert "if: vars.DEPLOY_ENABLED == 'true'" in block.split("steps:")[0], job
    assert "id-token: write" in DEPLOY and "secrets." not in DEPLOY


def test_all_actions_pinned_to_full_sha():
    for wf in (ROOT / ".github/workflows").glob("*.yml"):
        for ref in re.findall(r"uses:\s*[\w.-]+/[\w./-]+@(\S+)", wf.read_text()):
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (wf.name, ref)
