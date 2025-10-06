#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Hotel Key Card System
Tests all CRUD operations: Add, Update, Delete, View
"""

import os
import sys
from datetime import datetime

# Import the hotel module
from hotel import HotelService, CLI, ROOM_ACTIVE_VACANT, ROOM_ACTIVE_OCCUPIED, GUEST_ACTIVE, STAY_OPEN, KEYCARD_ACTIVE

def test_add_operations():
    """Test Add functionality"""
    print("\n" + "="*60)
    print("Testing ADD Operations")
    print("="*60)
    
    svc = HotelService()
    
    # Test 1: Add Room
    print("\n[Test 1] Adding a room...")
    room = svc.add_room("DELUXE", 3, 2, 2)
    assert room is not None, "Failed to add room"
    assert room.room_type == "DELUXE", "Room type mismatch"
    assert room.floor == 3, "Floor mismatch"
    assert room.status == ROOM_ACTIVE_VACANT, "Room status should be vacant"
    print(f"✓ Room added successfully: {room}")
    
    # Test 2: Add Guest
    print("\n[Test 2] Adding a guest...")
    guest = svc.add_guest("Test User", "0801234567", "T123456789")
    assert guest is not None, "Failed to add guest"
    assert guest.full_name == "Test User", "Guest name mismatch"
    assert guest.status == GUEST_ACTIVE, "Guest status should be active"
    print(f"✓ Guest added successfully: {guest}")
    
    # Test 3: Add Keycard
    print("\n[Test 3] Adding a keycard...")
    keycard = svc.add_keycard(room.room_id, "TEST12345")
    assert keycard is not None, "Failed to add keycard"
    assert keycard.serial == "TEST12345", "Keycard serial mismatch"
    assert keycard.status == KEYCARD_ACTIVE, "Keycard status should be active"
    print(f"✓ Keycard added successfully: {keycard}")
    
    # Test 4: Check-in (creates Stay)
    print("\n[Test 4] Performing check-in...")
    stay = svc.checkin(guest.guest_id, room.room_id, "2024-01-15", 2)
    assert stay is not None, "Failed to check-in"
    assert stay.status == STAY_OPEN, "Stay status should be open"
    assert stay.cards_issued == 2, "Cards issued mismatch"
    print(f"✓ Check-in successful: {stay}")
    
    # Verify room status changed to occupied
    rooms = svc.get_rooms()
    updated_room = next((r for r in rooms if r.room_id == room.room_id), None)
    assert updated_room.status == ROOM_ACTIVE_OCCUPIED, "Room should be occupied after check-in"
    print(f"✓ Room status changed to occupied")
    
    print("\n✅ All ADD tests passed!")
    return svc, room, guest, stay

def test_view_operations(svc):
    """Test View functionality"""
    print("\n" + "="*60)
    print("Testing VIEW Operations")
    print("="*60)
    
    # Test 1: View all rooms
    print("\n[Test 1] Viewing all rooms...")
    rooms = svc.get_rooms()
    assert len(rooms) > 0, "No rooms found"
    print(f"✓ Found {len(rooms)} room(s)")
    
    # Test 2: View all guests
    print("\n[Test 2] Viewing all guests...")
    guests = svc.get_guests()
    assert len(guests) > 0, "No guests found"
    print(f"✓ Found {len(guests)} guest(s)")
    
    # Test 3: View all stays
    print("\n[Test 3] Viewing all stays...")
    stays = svc.get_stays()
    assert len(stays) > 0, "No stays found"
    print(f"✓ Found {len(stays)} stay(s)")
    
    # Test 4: View all keycards
    print("\n[Test 4] Viewing all keycards...")
    keycards = svc.get_keycards()
    assert len(keycards) > 0, "No keycards found"
    print(f"✓ Found {len(keycards)} keycard(s)")
    
    # Test 5: View keycards by room
    print("\n[Test 5] Viewing keycards by room...")
    room = rooms[0]
    room_keycards = svc.get_keycards_by_room(room.room_id)
    print(f"✓ Found {len(room_keycards)} keycard(s) for room {room.room_id}")
    
    # Test 6: Test CLI _format_table with empty rows
    print("\n[Test 6] Testing _format_table with empty rows...")
    cli = CLI(svc)
    headers = ["ID", "Name", "Status"]
    empty_result = cli._format_table(headers, [])
    assert "ID" in empty_result, "_format_table should handle empty rows"
    print(f"✓ _format_table handles empty rows correctly")
    
    # Test 7: Test _format_table with mismatched columns
    print("\n[Test 7] Testing _format_table with mismatched columns...")
    rows = [["1", "Test"], ["2", "Test2", "Extra"]]
    result = cli._format_table(headers, rows)
    assert "ID" in result, "_format_table should handle mismatched columns"
    print(f"✓ _format_table handles mismatched columns correctly")
    
    print("\n✅ All VIEW tests passed!")

def test_update_operations(svc, room, guest, stay):
    """Test Update functionality"""
    print("\n" + "="*60)
    print("Testing UPDATE Operations")
    print("="*60)
    
    # Test 1: Update Room
    print("\n[Test 1] Updating room...")
    updated_room = svc.update_room(room.room_id, room_type="SUITE", capacity=4)
    assert updated_room is not None, "Failed to update room"
    assert updated_room.room_type == "SUITE", "Room type not updated"
    assert updated_room.capacity == 4, "Capacity not updated"
    print(f"✓ Room updated successfully: {updated_room}")
    
    # Test 2: Update Guest
    print("\n[Test 2] Updating guest...")
    updated_guest = svc.update_guest(guest.guest_id, phone="0809999999")
    assert updated_guest is not None, "Failed to update guest"
    assert updated_guest.phone == "0809999999", "Phone not updated"
    print(f"✓ Guest updated successfully: {updated_guest}")
    
    # Test 3: Update Keycard
    print("\n[Test 3] Updating keycard...")
    keycards = svc.get_keycards()
    if keycards:
        kc = keycards[0]
        updated_kc = svc.update_keycard(kc.keycard_id, serial="UPDATED123")
        assert updated_kc is not None, "Failed to update keycard"
        assert updated_kc.serial == "UPDATED123", "Serial not updated"
        print(f"✓ Keycard updated successfully: {updated_kc}")
    
    # Test 4: Check-out (Update Stay)
    print("\n[Test 4] Performing check-out...")
    result = svc.checkout(stay.stay_id, "2024-01-20")
    assert result == True, "Failed to check-out"
    
    # Verify stay status changed
    stays = svc.get_stays(include_deleted=True)
    updated_stay = next((s for s in stays if s.stay_id == stay.stay_id), None)
    assert updated_stay.checkout_date == "2024-01-20", "Checkout date not set"
    print(f"✓ Check-out successful, room should be vacant now")
    
    print("\n✅ All UPDATE tests passed!")

def test_delete_operations(svc, room, guest, stay):
    """Test Delete (soft delete) functionality"""
    print("\n" + "="*60)
    print("Testing DELETE Operations")
    print("="*60)
    
    # Test 1: Delete Keycard
    print("\n[Test 1] Deleting keycard...")
    keycards = svc.get_keycards(include_deleted=False)
    if keycards:
        kc = keycards[0]
        result = svc.delete_keycard(kc.keycard_id)
        assert result == True, "Failed to delete keycard"
        
        # Verify soft delete
        all_keycards = svc.get_keycards(include_deleted=True)
        deleted_kc = next((k for k in all_keycards if k.keycard_id == kc.keycard_id), None)
        assert deleted_kc.status == 0, "Keycard should be soft deleted"
        print(f"✓ Keycard soft deleted successfully")
    
    # Test 2: Delete Stay
    print("\n[Test 2] Deleting stay...")
    result = svc.delete_stay(stay.stay_id)
    assert result == True, "Failed to delete stay"
    
    # Verify soft delete
    all_stays = svc.get_stays(include_deleted=True)
    deleted_stay = next((s for s in all_stays if s.stay_id == stay.stay_id), None)
    assert deleted_stay.status == 9, "Stay should be soft deleted (status=9)"
    print(f"✓ Stay soft deleted successfully")
    
    # Test 3: Delete Guest
    print("\n[Test 3] Deleting guest...")
    result = svc.delete_guest(guest.guest_id)
    assert result == True, "Failed to delete guest"
    
    # Verify soft delete
    all_guests = svc.get_guests(include_deleted=True)
    deleted_guest = next((g for g in all_guests if g.guest_id == guest.guest_id), None)
    assert deleted_guest.status == 0, "Guest should be soft deleted"
    print(f"✓ Guest soft deleted successfully")
    
    # Test 4: Delete Room
    print("\n[Test 4] Deleting room...")
    result = svc.delete_room(room.room_id)
    assert result == True, "Failed to delete room"
    
    # Verify soft delete
    all_rooms = svc.get_rooms(include_deleted=True)
    deleted_room = next((r for r in all_rooms if r.room_id == room.room_id), None)
    assert deleted_room.status == 0, "Room should be soft deleted"
    print(f"✓ Room soft deleted successfully")
    
    print("\n✅ All DELETE tests passed!")

def test_report_generation(svc):
    """Test Report generation"""
    print("\n" + "="*60)
    print("Testing REPORT Generation")
    print("="*60)
    
    from hotel import Report, REPORT_DIR
    
    print("\n[Test 1] Generating report...")
    rep = Report(svc)
    report_text = rep.build_text()
    assert len(report_text) > 0, "Report text is empty"
    assert "Hotel Key Card System" in report_text, "Report header missing"
    print(f"✓ Report generated successfully ({len(report_text)} characters)")
    
    print("\n[Test 2] Saving report to file...")
    path = os.path.join(REPORT_DIR, "test_report.txt")
    saved_path = rep.save(path)
    assert os.path.exists(saved_path), "Report file not created"
    
    # Verify file content
    with open(saved_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 0, "Report file is empty"
    assert "Hotel Key Card System" in content, "Report content missing"
    print(f"✓ Report saved successfully to {saved_path}")
    
    print("\n✅ All REPORT tests passed!")

def main():
    print("\n" + "="*60)
    print("Hotel Key Card System - Comprehensive Test Suite")
    print("="*60)
    
    try:
        # Run all tests
        svc, room, guest, stay = test_add_operations()
        test_view_operations(svc)
        test_update_operations(svc, room, guest, stay)
        test_delete_operations(svc, room, guest, stay)
        test_report_generation(svc)
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
        print("="*60)
        print("\nSummary:")
        print("✅ ADD operations: Working correctly")
        print("✅ UPDATE operations: Working correctly")
        print("✅ DELETE operations: Working correctly (soft delete)")
        print("✅ VIEW operations: Working correctly")
        print("✅ REPORT generation: Working correctly")
        print("\nThe hotel management system is ready to use!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
