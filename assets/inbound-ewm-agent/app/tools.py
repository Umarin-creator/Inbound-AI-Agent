"""LangChain tools wrapping the EWM Inbound Actions REST API.

All tools use a module-level EwmActionsClient singleton.  Each tool returns
a JSON string so the LLM receives structured data it can reason about.
"""
import json
import logging
from typing import Optional

from langchain_core.tools import tool

from ewm_actions_client import EwmActionsClient

logger = logging.getLogger(__name__)

_client = EwmActionsClient()


def _ok(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _err(operation: str, exc: Exception) -> str:
    logger.error("%s failed: %s", operation, exc, exc_info=True)
    return json.dumps({"error": str(exc), "operation": operation})


@tool
async def ewm_read_transport_unit(
    tu_identifier: str,
    warehouse_number: str,
    dock_door: Optional[str] = None,
) -> str:
    """Get details of a Transport Unit (TU) in EWM.

    Returns the TU record including linked inbound deliveries.
    Use this to identify which deliveries arrived with a physical truck or container.

    Args:
        tu_identifier: The Transport Unit number (scanned or typed by the operator).
        warehouse_number: The EWM warehouse number the TU is arriving at.
        dock_door: Optional dock door identifier where the TU is physically present.
    """
    try:
        params = {"warehouseNumber": warehouse_number}
        if dock_door:
            params["dockDoor"] = dock_door
        result = await _client.get(f"/transport-units/{tu_identifier}", params=params)
        return _ok(result)
    except Exception as exc:
        return _err("ewm_read_transport_unit", exc)


@tool
async def ewm_read_inbound_delivery(
    delivery_number: str,
    warehouse_number: str,
) -> str:
    """Get details of an inbound delivery from EWM.

    Returns the delivery record including items, warehouse orders, and current EWM status.
    Use this to determine the current state of the delivery and the next required step.

    Args:
        delivery_number: The inbound delivery document number.
        warehouse_number: The EWM warehouse number the delivery belongs to.
    """
    try:
        params = {"warehouseNumber": warehouse_number}
        result = await _client.get(f"/deliveries/{delivery_number}", params=params)
        return _ok(result)
    except Exception as exc:
        return _err("ewm_read_inbound_delivery", exc)


@tool
async def ewm_post_goods_receipt(
    delivery_number: str,
    warehouse_number: str,
    operator_id: str,
    posting_date: str,
) -> str:
    """Post a Goods Receipt (GR) for an inbound delivery in EWM.

    This is a non-reversible write operation (AG-01). Always present a Confirmation
    Card to the operator and wait for explicit confirmation before calling this tool.

    Args:
        delivery_number: The inbound delivery document number.
        warehouse_number: The EWM warehouse number.
        operator_id: SAP user ID of the warehouse operator performing the GR.
        posting_date: GR posting date in ISO 8601 format (YYYY-MM-DD). Use today's date.
    """
    try:
        body = {
            "warehouseNumber": warehouse_number,
            "postingDate": posting_date,
            "operatorId": operator_id,
        }
        result = await _client.post(
            f"/deliveries/{delivery_number}/goods-receipt", body=body
        )
        return _ok(result)
    except Exception as exc:
        return _err("ewm_post_goods_receipt", exc)


@tool
async def ewm_create_putaway_tasks(
    delivery_number: str,
    warehouse_number: str,
) -> str:
    """Create putaway Warehouse Tasks (WTs) for an inbound delivery in EWM.

    Triggers EWM to generate putaway tasks for all open items in the delivery.
    This is a reversible write operation (AG-02). Always present a Confirmation
    Card to the operator before calling this tool.

    Args:
        delivery_number: The inbound delivery document number.
        warehouse_number: The EWM warehouse number.
    """
    try:
        body = {"warehouseNumber": warehouse_number}
        result = await _client.post(
            f"/deliveries/{delivery_number}/putaway-tasks", body=body
        )
        return _ok(result)
    except Exception as exc:
        return _err("ewm_create_putaway_tasks", exc)


@tool
async def ewm_validate_scan(
    warehouse_task: str,
    scan_value: str,
    expected_type: str,
    warehouse_number: str,
) -> str:
    """Validate a barcode scan against the expected value for a Warehouse Task.

    Use this whenever the operator scans a barcode to verify a material, HU, or bin.
    Returns whether the scan matches and what was expected vs. scanned.

    Args:
        warehouse_task: The Warehouse Task number being confirmed.
        scan_value: The raw value the operator scanned.
        expected_type: The type of entity being scanned (e.g. "HU", "MATERIAL", "BIN").
        warehouse_number: The EWM warehouse number.
    """
    try:
        body = {
            "scanValue": scan_value,
            "expectedType": expected_type,
            "warehouseNumber": warehouse_number,
        }
        result = await _client.post(
            f"/warehouse-tasks/{warehouse_task}/validate-scan", body=body
        )
        return _ok(result)
    except Exception as exc:
        return _err("ewm_validate_scan", exc)


@tool
async def ewm_confirm_warehouse_task(
    warehouse_task: str,
    warehouse_number: str,
    operator_id: str,
    confirmed_quantity: float,
    destination_bin: str,
) -> str:
    """Confirm a Warehouse Task (WT) in EWM, recording the actual quantity and bin.

    This is a non-reversible write operation (AG-03/AG-04). Always present a
    Confirmation Card and wait for operator approval before calling this tool.

    Args:
        warehouse_task: The Warehouse Task number to confirm.
        warehouse_number: The EWM warehouse number.
        operator_id: SAP user ID of the warehouse operator confirming the task.
        confirmed_quantity: The actual quantity placed into the destination bin.
        destination_bin: The storage bin where the stock was physically placed.
    """
    try:
        body = {
            "warehouseNumber": warehouse_number,
            "confirmedQuantity": confirmed_quantity,
            "destinationBin": destination_bin,
            "operatorId": operator_id,
        }
        result = await _client.post(
            f"/warehouse-tasks/{warehouse_task}/confirm", body=body
        )
        return _ok(result)
    except Exception as exc:
        return _err("ewm_confirm_warehouse_task", exc)


@tool
async def ewm_analyse_exception(
    delivery_number: str,
    warehouse_number: str,
    exception_description: str,
    ewm_error_code: Optional[str] = None,
    current_task: Optional[str] = None,
) -> str:
    """Analyse an EWM exception and retrieve ranked resolution options.

    Call this whenever a tool returns an error or the operator reports a problem.
    Returns the exception code, plain-language description, root cause, and up to
    three resolution options.

    Args:
        delivery_number: The inbound delivery document number affected by the exception.
        warehouse_number: The EWM warehouse number.
        exception_description: Plain-language description of what went wrong.
        ewm_error_code: Raw EWM/ABAP error code from a failed tool response, if available.
        current_task: The Warehouse Task number being processed when the exception occurred.
    """
    try:
        body: dict = {
            "exceptionDescription": exception_description,
            "deliveryNumber": delivery_number,
            "warehouseNumber": warehouse_number,
        }
        if ewm_error_code:
            body["ewmErrorCode"] = ewm_error_code
        if current_task:
            body["currentTask"] = current_task
        result = await _client.post("/exceptions/analyse", body=body)
        return _ok(result)
    except Exception as exc:
        return _err("ewm_analyse_exception", exc)


@tool
async def ewm_execute_exception_resolution(
    delivery_number: str,
    warehouse_number: str,
    resolution_code: str,
    operator_id: str,
    warehouse_task: Optional[str] = None,
    resolution_parameters: Optional[dict] = None,
) -> str:
    """Execute a chosen exception resolution in EWM.

    Call this after the operator has selected a resolution option from the
    Exception Card and confirmed via a Confirmation Card (AG-07).

    Args:
        delivery_number: The inbound delivery document number.
        warehouse_number: The EWM warehouse number.
        resolution_code: The resolution code selected by the operator.
        operator_id: SAP user ID of the warehouse operator approving the resolution.
        warehouse_task: The Warehouse Task number, if the exception is task-specific.
        resolution_parameters: Additional key-value parameters required by the resolution.
    """
    try:
        body: dict = {
            "resolutionCode": resolution_code,
            "deliveryNumber": delivery_number,
            "warehouseNumber": warehouse_number,
            "operatorId": operator_id,
        }
        if warehouse_task:
            body["warehouseTask"] = warehouse_task
        if resolution_parameters:
            body["resolutionParameters"] = resolution_parameters
        result = await _client.post("/exceptions/resolve", body=body)
        return _ok(result)
    except Exception as exc:
        return _err("ewm_execute_exception_resolution", exc)


@tool
async def ewm_escalate(
    delivery_number: str,
    warehouse_number: str,
    escalation_reason: str,
    operator_id: str,
    resolution_attempts: Optional[list] = None,
    warehouse_task: Optional[str] = None,
) -> str:
    """Escalate an unresolved exception to a supervisor in EWM.

    Auto-escalate when: two resolution attempts failed, exception type is EX-010,
    quantity discrepancy exceeds threshold, or the operator explicitly requests
    supervisor involvement. Always present a Confirmation Card (AG-08) first.

    Args:
        delivery_number: The inbound delivery document number.
        warehouse_number: The EWM warehouse number.
        escalation_reason: Plain-language description of why escalation is needed.
        operator_id: SAP user ID of the warehouse operator requesting escalation.
        resolution_attempts: List of resolution codes already tried (for supervisor context).
        warehouse_task: The Warehouse Task number, if task-specific.
    """
    try:
        body: dict = {
            "escalationReason": escalation_reason,
            "deliveryNumber": delivery_number,
            "warehouseNumber": warehouse_number,
            "operatorId": operator_id,
        }
        if resolution_attempts:
            body["resolutionAttempts"] = resolution_attempts
        if warehouse_task:
            body["warehouseTask"] = warehouse_task
        result = await _client.post("/escalations", body=body)
        return _ok(result)
    except Exception as exc:
        return _err("ewm_escalate", exc)


ALL_TOOLS = [
    ewm_read_transport_unit,
    ewm_read_inbound_delivery,
    ewm_post_goods_receipt,
    ewm_create_putaway_tasks,
    ewm_validate_scan,
    ewm_confirm_warehouse_task,
    ewm_analyse_exception,
    ewm_execute_exception_resolution,
    ewm_escalate,
]
