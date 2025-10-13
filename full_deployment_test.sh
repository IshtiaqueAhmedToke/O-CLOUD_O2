#!/bin/bash

echo "=========================================="
echo "  Full O2 DMS Deployment Test"
echo "  Testing with Mock O-DU"
echo "=========================================="
echo ""

BASE_URL="http://localhost:5001"  # Test port
PASS=0
FAIL=0

test_step() {
    local step=$1
    local name=$2
    echo "[$step] $name"
}

success() {
    echo "    ✅ PASS"
    ((PASS++))
}

fail() {
    echo "    ❌ FAIL: $1"
    ((FAIL++))
}

# Test 1: O2 Interface responding
test_step "1" "Testing O2 Interface availability"
if curl -s -f $BASE_URL/health > /dev/null; then
    success
else
    fail "O2 Interface not responding"
    echo "    Make sure o2_interface_test.py is running on port 5001"
    exit 1
fi
echo ""

# Test 2: Check test mode
test_step "2" "Verifying test mode configuration"
response=$(curl -s $BASE_URL/)
if echo "$response" | grep -q "TEST MODE"; then
    success
    echo "    Running in TEST MODE (correct)"
else
    fail "Not in test mode"
fi
echo ""

# Test 3: Resource discovery
test_step "3" "Testing resource discovery (O2 IMS)"
resources=$(curl -s $BASE_URL/o2ims-infrastructureInventory/v1/resourcePools)
if echo "$resources" | grep -q "pool-001"; then
    success
    echo "$resources" | python3 -c "
import sys, json
data = json.load(sys.stdin)
res = data[0]['resources']
print(f\"    Resources: {res['cpu']['total_cores']} cores, {res['memory']['total_mb']} MB RAM\")
"
else
    fail "Resource discovery failed"
fi
echo ""

# Test 4: Check deployment managers
test_step "4" "Testing deployment managers (O2 IMS)"
dm=$(curl -s $BASE_URL/o2ims-infrastructureInventory/v1/deploymentManagers)
if echo "$dm" | grep -q "Mock Process Manager"; then
    success
    echo "    Mock deployment manager available"
else
    fail "Deployment manager not found"
fi
echo ""

# Test 5: List deployments (should be empty initially)
test_step "5" "Testing deployment listing (O2 DMS)"
deps=$(curl -s $BASE_URL/o2dms-deploymentManagement/v1/deployments)
if [ "$deps" == "[]" ]; then
    success
    echo "    No deployments (expected)"
else
    echo "    ⚠️  Found existing deployment - will clean up"
    curl -s -X DELETE $BASE_URL/o2dms-deploymentManagement/v1/deployments/dep-du-001 > /dev/null
    sleep 2
    success
fi
echo ""

# Test 6: Deploy Mock O-DU
test_step "6" "Testing deployment creation (O2 DMS POST)"
response=$(curl -s -w "\n%{http_code}" -X POST $BASE_URL/o2dms-deploymentManagement/v1/deployments \
  -H "Content-Type: application/json" \
  -d '{"type": "O-DU"}')

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" == "201" ]; then
    success
    echo "    Deployment created successfully"
    DEPLOYED=true
    
    # Extract deployment details
    echo "$body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"    Deployment ID: {data.get('deploymentId', 'unknown')}\")
print(f\"    Process ID: {data.get('pid', 'unknown')}\")
print(f\"    Status: {data.get('status', 'unknown')}\")
print(f\"    Log File: {data.get('logFile', 'unknown')}\")
"
else
    fail "Deployment failed with HTTP $http_code"
    echo "$body"
    DEPLOYED=false
fi
echo ""

# Only continue if deployment succeeded
if [ "$DEPLOYED" == "true" ]; then
    # Wait for mock O-DU to fully start
    echo "Waiting 3 seconds for Mock O-DU to initialize..."
    sleep 3
    echo ""

    # Test 7: Verify deployment in list
    test_step "7" "Verifying deployment appears in list"
    deps=$(curl -s $BASE_URL/o2dms-deploymentManagement/v1/deployments)
    if echo "$deps" | grep -q "dep-du-001"; then
        success
        echo "$deps" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data:
    dep = data[0]
    print(f\"    Name: {dep.get('name', 'unknown')}\")
    print(f\"    Type: {dep.get('type', 'unknown')}\")
    print(f\"    Status: {dep.get('status', 'unknown')}\")
    print(f\"    Operational State: {dep.get('operationalState', 'unknown')}\")
    print(f\"    PID: {dep.get('pid', 'unknown')}\")
"
    else
        fail "Deployment not in list"
    fi
    echo ""

    # Test 8: Check specific deployment details
    test_step "8" "Testing deployment details (GET by ID)"
    dep_detail=$(curl -s $BASE_URL/o2dms-deploymentManagement/v1/deployments/dep-du-001)
    if echo "$dep_detail" | grep -q "dep-du-001"; then
        success
        echo "$dep_detail" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"    Deployment ID: {data.get('deploymentId', 'unknown')}\")
print(f\"    Operational State: {data.get('operationalState', 'unknown')}\")
"
    else
        fail "Cannot get deployment details"
    fi
    echo ""

    # Test 9: Verify health includes deployment
    test_step "9" "Verifying deployment in health endpoint"
    health=$(curl -s $BASE_URL/health)
    if echo "$health" | grep -q "mock_o_du_running"; then
        running=$(echo "$health" | python3 -c "import sys, json; print(json.load(sys.stdin).get('mock_o_du_running', False))")
        if [ "$running" == "True" ]; then
            success
            echo "    Mock O-DU reported as running in health check"
            pid=$(echo "$health" | python3 -c "import sys, json; print(json.load(sys.stdin).get('mock_o_du_pid', 'N/A'))")
            echo "    PID: $pid"
        else
            fail "Mock O-DU not running according to health check"
        fi
    else
        fail "Health check missing Mock O-DU status"
    fi
    echo ""

    # Test 10: Check the actual log file
    test_step "10" "Checking Mock O-DU log output"
    LOG_FILE="$HOME/o-cloud/testing/logs/mock_du.log"
    if [ -f "$LOG_FILE" ]; then
        success
        echo "    Log file exists: $LOG_FILE"
        echo "    Last few lines:"
        tail -n 3 "$LOG_FILE" | sed 's/^/    │ /'
    else
        fail "Log file not found at $LOG_FILE"
    fi
    echo ""

    # Test 11: Verify status endpoint includes deployment
    test_step "11" "Testing comprehensive status endpoint"
    status=$(curl -s $BASE_URL/status)
    dep_count=$(echo "$status" | python3 -c "import sys, json; print(json.load(sys.stdin)['deployments']['count'])")
    if [ "$dep_count" == "1" ]; then
        success
        echo "    Deployment count: $dep_count (correct)"
    else
        fail "Expected 1 deployment, got $dep_count"
    fi
    echo ""

    # Test 12: Stop deployment
    test_step "12" "Testing deployment deletion (DELETE)"
    del_response=$(curl -s -w "\n%{http_code}" -X DELETE $BASE_URL/o2dms-deploymentManagement/v1/deployments/dep-du-001)
    del_code=$(echo "$del_response" | tail -n1)
    
    if [ "$del_code" == "200" ]; then
        success
        echo "    Deployment stopped successfully"
    else
        fail "Failed to stop deployment (HTTP $del_code)"
    fi
    echo ""

    # Wait for process to terminate
    echo "Waiting 2 seconds for cleanup..."
    sleep 2
    echo ""

    # Test 13: Verify deployment removed
    test_step "13" "Verifying deployment removed from list"
    deps=$(curl -s $BASE_URL/o2dms-deploymentManagement/v1/deployments)
    if [ "$deps" == "[]" ]; then
        success
        echo "    Deployment list empty (expected)"
    else
        fail "Deployment still in list"
        echo "$deps"
    fi
    echo ""

    # Test 14: Verify health reflects stopped state
    test_step "14" "Verifying health reflects stopped state"
    health=$(curl -s $BASE_URL/health)
    running=$(echo "$health" | python3 -c "import sys, json; print(json.load(sys.stdin).get('mock_o_du_running', True))")
    if [ "$running" == "False" ]; then
        success
        echo "    Mock O-DU correctly reported as not running"
    else
        fail "Mock O-DU still reported as running"
    fi
else
    echo ""
    echo "⚠️  Deployment failed - skipping subsequent tests"
    echo "Check that mock_odu.py exists and is executable"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Results: $PASS passed, $FAIL failed"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo ""
    echo "🎉 ALL TESTS PASSED! 🎉"
    echo ""
    echo "Your O2 DMS deployment functionality is working perfectly!"
    echo ""
    echo "What was tested:"
    echo "  ✅ O2 Interface connectivity"
    echo "  ✅ Resource discovery (O2 IMS)"
    echo "  ✅ Deployment managers"
    echo "  ✅ Deployment lifecycle (CREATE)"
    echo "  ✅ Deployment verification"
    echo "  ✅ Health monitoring integration"
    echo "  ✅ Status reporting"
    echo "  ✅ Deployment lifecycle (DELETE)"
    echo "  ✅ Cleanup verification"
    echo ""
    echo "When you have access to the lab:"
    echo "  1. Use the original o2_interface_with_du.py"
    echo "  2. Update DU_PATH to real srsRAN binary"
    echo "  3. Update DU_CONFIG with actual gnb_du.yml"
    echo "  4. Update CU IP in the config"
    echo "  5. Deploy using the same API calls"
    echo ""
    echo "The deployment logic is IDENTICAL - only the binary changes!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed"
    echo ""
    echo "Common issues:"
    echo "  • Make sure o2_interface_test.py is running on port 5001"
    echo "  • Check that mock_odu.py exists and is executable"
    echo "  • Verify ~/o-cloud/testing/logs/ directory exists"
    echo ""
    exit 1
fi
