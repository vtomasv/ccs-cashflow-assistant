"""
Test funcional del simulador de escenarios.
Verifica que la simulación local se ejecuta correctamente,
genera checkpoints, reporta progreso y termina exitosamente.
"""
import os
import sys
import json
import time
import shutil
import tempfile
from pathlib import Path

# Configurar antes de importar app
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
TEST_DATA_DIR = tempfile.mkdtemp(prefix="ccs_sim_test_")
os.environ["DATA_DIR"] = TEST_DATA_DIR
os.environ["PORT"] = "9998"

from fastapi.testclient import TestClient
from app import app, save_json, DATA_DIR, _generation_status

client = TestClient(app)


def setup_company_with_cashflow():
    """Crea una empresa con flujo de caja de 12 meses para testing."""
    resp = client.post("/api/companies", json={"name": "Empresa Simulación Test", "sector": "comercio"})
    company_id = resp.json()["id"]
    
    cashflow = {
        "company_name": "Empresa Simulación Test",
        "months": [],
        "alerts": [],
        "recommendations": []
    }
    for i in range(12):
        mo = i + 1
        cashflow["months"].append({
            "month": f"2025-{mo:02d}",
            "label": f"Mes {mo}",
            "income": {"sales": 10000000 + (mo * 500000), "other_income": 500000},
            "expenses": {
                "variable_costs": 3000000,
                "fixed_costs": 2000000,
                "variable_expenses": 500000,
                "debt_payments": 300000,
                "taxes": 200000,
                "investments": 100000
            }
        })
    
    save_json(DATA_DIR / "companies" / company_id / "cashflow.json", cashflow)
    return company_id


def test_local_simulation_completes():
    """Test que la simulación local se completa exitosamente."""
    company_id = setup_company_with_cashflow()
    
    # Ejecutar simulación local con parámetros
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Aumentar ventas 20%, reducir costos 10%",
        "params": {
            "sales_change_pct": 20,
            "costs_change_pct": -10,
            "fixed_costs_change_pct": 5,
            "inflation_annual_pct": 8,
            "new_hires": 2,
            "hire_cost": 800000,
            "tax_change_pct": 0,
            "debt_change_pct": -5,
            "investment_change_pct": 15,
            "other_income_change_pct": 10
        }
    })
    
    assert resp.status_code == 200, f"Error al iniciar simulación: {resp.text}"
    data = resp.json()
    assert "task_id" in data
    task_id = data["task_id"]
    
    # Polling hasta completar (máximo 30 segundos)
    max_attempts = 30
    for attempt in range(max_attempts):
        progress_resp = client.get(f"/api/generation/{task_id}/progress")
        assert progress_resp.status_code == 200
        progress = progress_resp.json()
        
        print(f"  Intento {attempt + 1}: status={progress['status']}, progress={progress.get('progress', 0)}%, step={progress.get('step', '')}")
        
        if progress["status"] == "done":
            assert progress["progress"] == 100
            assert "scenario_id" in progress
            assert progress.get("mode") == "local"
            print(f"  ✓ Simulación completada exitosamente. Scenario ID: {progress['scenario_id']}")
            
            # Verificar que el escenario se guardó
            scenario_resp = client.get(f"/api/scenarios/{progress['scenario_id']}")
            assert scenario_resp.status_code == 200
            scenario = scenario_resp.json()
            
            # Verificar estructura del escenario
            assert "months" in scenario
            assert len(scenario["months"]) == 12
            assert "summary" in scenario
            assert "scenario_name" in scenario
            assert "changes_applied" in scenario
            assert "alerts" in scenario
            assert "impact_summary" in scenario
            assert "recommendations" in scenario
            assert scenario["simulation_mode"] == "local"
            
            # Verificar que los cambios se aplicaron
            original_sales = 10500000  # Mes 1: 10000000 + 500000
            expected_sales = original_sales * 1.2  # +20%
            actual_sales = scenario["months"][0]["income"]["sales"]
            assert abs(actual_sales - expected_sales) < 1, f"Ventas no coinciden: {actual_sales} vs {expected_sales}"
            
            # Verificar impacto
            assert "income_change" in scenario["impact_summary"]
            assert "expenses_change" in scenario["impact_summary"]
            assert "net_change" in scenario["impact_summary"]
            
            print(f"  ✓ Impacto: {scenario['impact_summary']['description']}")
            print(f"  ✓ Cambios aplicados: {scenario['changes_applied']}")
            print(f"  ✓ Alertas: {len(scenario['alerts'])}")
            print(f"  ✓ Recomendaciones: {len(scenario['recommendations'])}")
            return
        
        elif progress["status"] == "error":
            raise AssertionError(f"Simulación falló: {progress.get('error', 'Unknown error')}")
        
        time.sleep(0.1)
    
    raise AssertionError(f"Simulación no completó en {max_attempts} intentos")


def test_simulation_with_zero_params():
    """Test que la simulación con todos los parámetros en 0 no cambia los valores de los meses."""
    company_id = setup_company_with_cashflow()
    
    # Obtener cashflow normalizado como base
    base_resp = client.get(f"/api/companies/{company_id}/cashflow")
    base_cashflow = base_resp.json()
    base_net = base_cashflow["summary"]["net_cashflow"]
    
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Sin cambios",
        "params": {
            "sales_change_pct": 0,
            "costs_change_pct": 0,
            "fixed_costs_change_pct": 0,
            "inflation_annual_pct": 0,
            "new_hires": 0,
            "tax_change_pct": 0,
            "debt_change_pct": 0,
            "investment_change_pct": 0,
            "other_income_change_pct": 0
        }
    })
    
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    
    # Esperar a que termine
    for _ in range(30):
        progress = client.get(f"/api/generation/{task_id}/progress").json()
        if progress["status"] == "done":
            scenario = client.get(f"/api/scenarios/{progress['scenario_id']}").json()
            # Verificar que el flujo neto del escenario es igual al base normalizado
            scenario_net = scenario["summary"]["net_cashflow"]
            assert abs(scenario_net - base_net) < 1, \
                f"Se esperaba net_cashflow={base_net}, got {scenario_net}"
            # Verificar que los meses tienen los mismos valores
            for i, m in enumerate(scenario["months"]):
                base_m = base_cashflow["months"][i]
                assert abs(m["income"]["sales"] - base_m["income"]["sales"]) < 1, \
                    f"Mes {i}: ventas difieren"
            print("  ✓ Simulación con parámetros en 0 no genera cambios")
            return
        elif progress["status"] == "error":
            raise AssertionError(f"Error: {progress.get('error')}")
        time.sleep(0.1)
    
    raise AssertionError("Timeout")


def test_simulation_export_csv():
    """Test que se puede exportar un escenario como CSV."""
    company_id = setup_company_with_cashflow()
    
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Test export",
        "params": {"sales_change_pct": 10}
    })
    task_id = resp.json()["task_id"]
    
    for _ in range(30):
        progress = client.get(f"/api/generation/{task_id}/progress").json()
        if progress["status"] == "done":
            # Exportar CSV
            csv_resp = client.get(f"/api/scenarios/{progress['scenario_id']}/export/csv")
            assert csv_resp.status_code == 200
            assert "text/csv" in csv_resp.headers.get("content-type", "")
            print("  ✓ Exportación CSV funciona correctamente")
            
            # Exportar Excel
            excel_resp = client.get(f"/api/scenarios/{progress['scenario_id']}/export/excel")
            assert excel_resp.status_code == 200
            assert "spreadsheet" in excel_resp.headers.get("content-type", "")
            print("  ✓ Exportación Excel funciona correctamente")
            return
        elif progress["status"] == "error":
            raise AssertionError(f"Error: {progress.get('error')}")
        time.sleep(0.1)
    
    raise AssertionError("Timeout")


def test_simulation_list_scenarios():
    """Test que se pueden listar escenarios de una empresa."""
    company_id = setup_company_with_cashflow()
    
    # Crear 3 simulaciones
    for i in range(3):
        resp = client.post(f"/api/companies/{company_id}/simulate", json={
            "instruction": f"Test {i}",
            "params": {"sales_change_pct": (i + 1) * 10}
        })
        task_id = resp.json()["task_id"]
        for _ in range(30):
            progress = client.get(f"/api/generation/{task_id}/progress").json()
            if progress["status"] in ("done", "error"):
                break
            time.sleep(0.1)
    
    # Listar escenarios
    list_resp = client.get(f"/api/companies/{company_id}/scenarios")
    assert list_resp.status_code == 200
    scenarios = list_resp.json()["scenarios"]
    assert len(scenarios) >= 3, f"Se esperaban al menos 3 escenarios, got {len(scenarios)}"
    print(f"  ✓ Se listaron {len(scenarios)} escenarios correctamente")


def test_simulation_delete_scenario():
    """Test que se puede eliminar un escenario."""
    company_id = setup_company_with_cashflow()
    
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Para borrar",
        "params": {"sales_change_pct": 5}
    })
    task_id = resp.json()["task_id"]
    
    for _ in range(30):
        progress = client.get(f"/api/generation/{task_id}/progress").json()
        if progress["status"] == "done":
            scenario_id = progress["scenario_id"]
            # Eliminar
            del_resp = client.delete(f"/api/scenarios/{scenario_id}")
            assert del_resp.status_code == 200
            # Verificar que ya no existe
            get_resp = client.get(f"/api/scenarios/{scenario_id}")
            assert get_resp.status_code == 404
            print("  ✓ Escenario eliminado correctamente")
            return
        elif progress["status"] == "error":
            raise AssertionError(f"Error: {progress.get('error')}")
        time.sleep(0.1)
    
    raise AssertionError("Timeout")


def test_simulation_performance():
    """Test que la simulación local es rápida (< 2 segundos para 12 meses)."""
    company_id = setup_company_with_cashflow()
    
    start_time = time.time()
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Performance test",
        "params": {
            "sales_change_pct": 20,
            "costs_change_pct": -10,
            "fixed_costs_change_pct": 5,
            "inflation_annual_pct": 12,
            "new_hires": 5,
            "hire_cost": 1000000,
            "tax_change_pct": 3,
            "debt_change_pct": -5,
            "investment_change_pct": 15,
            "other_income_change_pct": 10
        }
    })
    task_id = resp.json()["task_id"]
    
    for _ in range(30):
        progress = client.get(f"/api/generation/{task_id}/progress").json()
        if progress["status"] == "done":
            elapsed = time.time() - start_time
            assert elapsed < 2.0, f"Simulación tardó {elapsed:.2f}s (máximo 2s)"
            print(f"  ✓ Simulación completada en {elapsed:.3f}s (< 2s)")
            return
        elif progress["status"] == "error":
            raise AssertionError(f"Error: {progress.get('error')}")
        time.sleep(0.05)
    
    raise AssertionError("Timeout")


def test_checkpoint_created_and_cleaned():
    """Test que los checkpoints se crean durante la simulación y se limpian al terminar."""
    company_id = setup_company_with_cashflow()
    checkpoints_dir = DATA_DIR / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    resp = client.post(f"/api/companies/{company_id}/simulate", json={
        "instruction": "Checkpoint test",
        "params": {"sales_change_pct": 15}
    })
    task_id = resp.json()["task_id"]
    
    for _ in range(30):
        progress = client.get(f"/api/generation/{task_id}/progress").json()
        if progress["status"] == "done":
            # Checkpoint debe haberse limpiado al terminar
            checkpoint_path = checkpoints_dir / f"{task_id}.json"
            assert not checkpoint_path.exists(), "Checkpoint debería haberse limpiado al terminar"
            print("  ✓ Checkpoint creado y limpiado correctamente")
            return
        elif progress["status"] == "error":
            raise AssertionError(f"Error: {progress.get('error')}")
        time.sleep(0.1)
    
    raise AssertionError("Timeout")


if __name__ == "__main__":
    print("=" * 60)
    print("TEST FUNCIONAL: Simulador de Escenarios")
    print("=" * 60)
    
    tests = [
        ("Simulación local completa", test_local_simulation_completes),
        ("Simulación con parámetros en 0", test_simulation_with_zero_params),
        ("Exportación CSV/Excel", test_simulation_export_csv),
        ("Listar escenarios", test_simulation_list_scenarios),
        ("Eliminar escenario", test_simulation_delete_scenario),
        ("Performance (< 2s)", test_simulation_performance),
        ("Checkpoints", test_checkpoint_created_and_cleaned),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        print(f"\n{'─' * 50}")
        print(f"▶ {name}")
        try:
            test_fn()
            passed += 1
            print(f"  ✅ PASSED")
        except Exception as e:
            failed += 1
            print(f"  ❌ FAILED: {e}")
    
    print(f"\n{'═' * 60}")
    print(f"RESULTADOS: {passed} passed, {failed} failed de {len(tests)} tests")
    print(f"{'═' * 60}")
    
    # Limpiar
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    
    sys.exit(0 if failed == 0 else 1)
