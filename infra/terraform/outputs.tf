output "resource_group" {
  description = "Resource group name."
  value       = azurerm_resource_group.rg.name
}

output "workspace_name" {
  description = "Azure ML workspace name."
  value       = azapi_resource.mlw.name
}

output "endpoint_name" {
  description = "Managed online endpoint name."
  value       = azapi_resource.endpoint.name
}

output "key_vault_name" {
  description = "Key Vault for connector secrets."
  value       = azurerm_key_vault.kv.name
}
