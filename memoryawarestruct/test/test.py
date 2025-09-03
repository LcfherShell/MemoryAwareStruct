from memoryawarestruct.core.memory import memory

if __name__ == "__main__":
    print("=== Testing Enhanced Secure Struct with Attribute Protection ===")

    # Test 1: Normal usage
    print("\n1. Normal Usage:")
    struct = memory(name="John", age=30, city="Jakarta")
    print(f"Created: {struct}")
    print(f"Protection status: {struct.get_protection_status()}")

    # Test 2: Try to modify attribute directly (should fail)
    print("\n2. Trying to modify attribute directly:")
    try:
        struct.name = "HACKED"
        print(f"After direct modification: {struct.name}")
        print("ERROR: Direct attribute modification succeeded (THIS SHOULD NOT HAPPEN)")
    except AttributeError as e:
        print(f"SUCCESS: Direct attribute modification blocked: {e}")

    # Test 3: Try to delete attribute directly (should fail)
    print("\n3. Trying to delete attribute directly:")
    try:
        del struct.age
        print("ERROR: Direct attribute deletion succeeded (THIS SHOULD NOT HAPPEN)")
    except AttributeError as e:
        print(f"SUCCESS: Direct attribute deletion blocked: {e}")

    # Test 4: Using safe methods (should work)
    print("\n4. Using safe methods:")
    success = struct.safe_set("name", "Jane")
    print(f"safe_set result: {success}")
    print(f"Name after safe_set: {struct.name}")

    success = struct.dell_dict("city")
    print(f"dell_dict result: {success}")
    print(f"Struct after dell_dict: {struct}")

    # Test 5: Try to modify __dict__ directly (should fail)
    print("\n5. Trying to modify __dict__ directly:")
    try:
        struct.__dict__["name"] = "HACKED"
        print("ERROR: Dict modification succeeded (THIS SHOULD NOT HAPPEN)")
    except (AttributeError, TypeError) as e:
        print(f"SUCCESS: Dict modification blocked: {e}")

    # Test 6: Additional protection tests
    print("\n6. Additional protection tests:")

    # Try to add new attribute directly (should fail if it becomes user attribute)
    print("6a. Trying to add new attribute directly:")
    try:
        struct.new_attr = "test"
        print(f"New attribute added: {struct.new_attr}")
    except AttributeError as e:
        print(f"New attribute addition blocked: {e}")

    # But safe_set should work
    print("6b. Adding new attribute via safe_set:")
    success = struct.safe_set("new_attr", "test_safe")
    print(f"safe_set new attribute result: {success}")
    if hasattr(struct, "new_attr"):
        print(f"New attribute value: {struct.new_attr}")

    # Now try to modify the new attribute directly (should fail)
    print("6c. Trying to modify new attribute directly:")
    try:
        struct["new_attr"] = "HACKED"
        print("ERROR: New attribute modification succeeded")
    except AttributeError as e:
        print(f"SUCCESS: New attribute modification blocked: {e}")
    # Final test
    print("\nFinal test")
    struct.insert_dict = [{"pangkat": [{"bintang": {"angkatan": 12}}, [8, 9], "hallo"]}]

    # struct.pangkat[0].bintang = 98
    print(struct.pangkat[0].bintang.angkatan)
    print(struct["name"])
