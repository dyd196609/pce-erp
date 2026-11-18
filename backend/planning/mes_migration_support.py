"""Selective native-table creation after all cyclic model states are registered."""
NAMES={'planning':['ProductionOperationReport','OperationQuantityAccount','OperationOutputEvidence','OperationOutputAllocation','OperationCustodySlice','OperationHandover','OperationHandoverAllocation','OperationCustodyEvent','OperationCustodyException','OperationInputAllocation','OperationCompletionGeneration'],'pde':['WorkCenterResponsibilityScope'],'workflow_runtime':['WorkflowClosure']}
def create_models(apps,schema_editor,app):
 existing=set(schema_editor.connection.introspection.table_names())
 for name in NAMES[app]:
  model=apps.get_model(app,name)
  if model._meta.db_table not in existing:schema_editor.create_model(model);existing.add(model._meta.db_table)
def create_planning(apps,schema_editor):create_models(apps,schema_editor,'planning')
def create_pde(apps,schema_editor):create_models(apps,schema_editor,'pde')
def create_workflow(apps,schema_editor):create_models(apps,schema_editor,'workflow_runtime')
