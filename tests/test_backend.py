from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Money Muling Forensics" in response.text

def test_e2e_detection():
    # Create a dummy CSV
    csv_content = """transaction_id,sender_id,receiver_id,amount,timestamp
T1,A,B,100,2023-01-01T10:00:00
T2,B,C,100,2023-01-01T10:05:00
T3,C,A,100,2023-01-01T10:10:00
T4,X,Y,50,2023-01-01T12:00:00
T5,X,Z,50,2023-01-01T12:00:00
T6,X,W,50,2023-01-01T12:00:00
T7,X,V,50,2023-01-01T12:00:00
T8,X,U,50,2023-01-01T12:00:00
T9,X,T,50,2023-01-01T12:00:00
T10,X,S,50,2023-01-01T12:00:00
T11,X,R,50,2023-01-01T12:00:00
T12,X,Q,50,2023-01-01T12:00:00
T13,X,P,50,2023-01-01T12:00:00
"""
    files = {"file": ("test.csv", csv_content, "text/csv")}
    response = client.post("/api/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "summary" in data
    
    # Check results endpoint
    res_response = client.get("/api/results")
    assert res_response.status_code == 200
    results = res_response.json()
    
    # Verify Cycle A->B->C->A
    rings = results["fraud_rings"]
    cycle_rings = [r for r in rings if "cycle" in r["pattern_type"]]
    assert len(cycle_rings) >= 1
    
    # Verify Smurfing (X Fan-out)
    suspicious = results["suspicious_accounts"]
    # Check if X is in suspicious
    x_suspect = next((s for s in suspicious if s["account_id"] == "X"), None)
    assert x_suspect is not None
    assert "fan_out_10_plus" in x_suspect["detected_patterns"] or 25 in x_suspect.values() # or similar check
    
    # Verify Graph Edges present
    assert "graph_edges" in results
    assert len(results["graph_edges"]) >= 13

if __name__ == "__main__":
    # If run directly
    test_read_main()
    test_e2e_detection()
    print("All tests passed!")
