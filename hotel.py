#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotel Key Card CLI — Binary File I/O (struct) / OOP / Standard Library Only
Python 3.10+

Files (fixed-length, little-endian '<'):
  data/rooms.dat   : master rooms
  data/guests.dat  : master guests
  data/stays.dat   : master stays (การเข้าพัก: Guest x Room)
  data/keycards.dat: master keycards

Report (text):
  reports/hotel_report.txt

Menus:
  1) Add     2) Update     3) Delete     4) View (single/all/filter/summary+report)     0) Exit

Notes
- Soft delete: status=0 (rooms/guests), stays: 9=Deleted, 1=Open, 0=Closed
- Strings are fixed-length bytes; padded with b'\x00' and trimmed on read
- This sample emphasizes correctness and clarity over concurrency/perf (single-process CLI)
"""

from __future__ import annotations
import os, io, struct, time, math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Iterable, List, Dict, Tuple
import argparse
from textwrap import dedent

# ----------------------------- Utilities -------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

def now_ts() -> int:
    return int(time.time())

def fmt_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def fix_bytes(s: str, size: int) -> bytes:
    b = s.encode("utf-8", errors="ignore")[:size]
    return b.ljust(size, b"\x00")

def read_str(b: bytes) -> str:
    return b.rstrip(b"\x00").decode("utf-8", errors="ignore")

# ----------------------------- Record Layouts (struct) ------------------------

# Room record (64 bytes)
# <II20sIIIII -> 4+4+20+4+4+4+4+4 = 48  (pad to 64 on disk)
ROOM_STRUCT = struct.Struct("<II20sIIIII")
ROOM_SIZE = 64

# Guest record (112 bytes)
# <II50s15s20sII -> 4+4+50+15+20+4+4 = 101 (pad 112)
GUEST_STRUCT = struct.Struct("<II50s15s20sII")
GUEST_SIZE = 112

# Stay record (64 bytes)
# <IIII10s10sIII -> 4+4+4+4+10+10+4+4+4 = 44 (pad 64)
STAY_STRUCT = struct.Struct("<IIII10s10sIII")
STAY_SIZE = 64

# Keycard record (32 bytes)
# <III10sII -> 4+4+4+10+4+4 = 30 (pad 32)
KEYCARD_STRUCT = struct.Struct("<III10sII")
KEYCARD_SIZE = 32

# Status constants
ROOM_DELETED = 0
ROOM_ACTIVE_VACANT = 1
ROOM_ACTIVE_OCCUPIED = 2

GUEST_DELETED = 0
GUEST_ACTIVE = 1

STAY_DELETED = 9
STAY_OPEN = 1
STAY_CLOSED = 0

KEYCARD_DELETED = 0
KEYCARD_ACTIVE = 1

# ----------------------------- Data Classes ----------------------------------

@dataclass
class Room:
    room_id: int
    status: int
    room_type: str
    floor: int
    capacity: int
    max_cards: int
    created_at: int
    updated_at: int

    def pack(self) -> bytes:
        raw = ROOM_STRUCT.pack(
            self.room_id,
            self.status,
            fix_bytes(self.room_type, 20),
            self.floor,
            self.capacity,
            self.max_cards,
            self.created_at,
            self.updated_at,
        )
        return raw.ljust(ROOM_SIZE, b"\x00")

    @staticmethod
    def unpack(buf: bytes) -> "Room":
        t = ROOM_STRUCT.unpack(buf[:ROOM_STRUCT.size])
        return Room(
            room_id=t[0],
            status=t[1],
            room_type=read_str(t[2]),
            floor=t[3],
            capacity=t[4],
            max_cards=t[5],
            created_at=t[6],
            updated_at=t[7],
        )

@dataclass
class Guest:
    guest_id: int
    status: int
    full_name: str
    phone: str
    id_no: str
    created_at: int
    updated_at: int

    def pack(self) -> bytes:
        raw = GUEST_STRUCT.pack(
            self.guest_id,
            self.status,
            fix_bytes(self.full_name, 50),
            fix_bytes(self.phone, 15),
            fix_bytes(self.id_no, 20),
            self.created_at,
            self.updated_at,
        )
        return raw.ljust(GUEST_SIZE, b"\x00")

    @staticmethod
    def unpack(buf: bytes) -> "Guest":
        t = GUEST_STRUCT.unpack(buf[:GUEST_STRUCT.size])
        return Guest(
            guest_id=t[0],
            status=t[1],
            full_name=read_str(t[2]),
            phone=read_str(t[3]),
            id_no=read_str(t[4]),
            created_at=t[5],
            updated_at=t[6],
        )

@dataclass
class Stay:
    stay_id: int
    status: int
    guest_id: int
    room_id: int
    checkin_date: str  # 'YYYY-MM-DD'
    checkout_date: str # 'YYYY-MM-DD' or empty
    cards_issued: int
    cards_returned: int
    updated_at: int

    def pack(self) -> bytes:
        raw = STAY_STRUCT.pack(
            self.stay_id,
            self.status,
            self.guest_id,
            self.room_id,
            fix_bytes(self.checkin_date, 10),
            fix_bytes(self.checkout_date, 10),
            self.cards_issued,
            self.cards_returned,
            self.updated_at,
        )
        return raw.ljust(STAY_SIZE, b"\x00")

    @staticmethod
    def unpack(buf: bytes) -> "Stay":
        t = STAY_STRUCT.unpack(buf[:STAY_STRUCT.size])
        return Stay(
            stay_id=t[0],
            status=t[1],
            guest_id=t[2],
            room_id=t[3],
            checkin_date=read_str(t[4]),
            checkout_date=read_str(t[5]),
            cards_issued=t[6],
            cards_returned=t[7],
            updated_at=t[8],
        )

@dataclass
class Keycard:
    keycard_id: int
    status: int
    room_id: int
    serial: str
    created_at: int
    updated_at: int

    def pack(self) -> bytes:
        raw = KEYCARD_STRUCT.pack(
            self.keycard_id,
            self.status,
            self.room_id,
            fix_bytes(self.serial, 10),
            self.created_at,
            self.updated_at,
        )
        return raw.ljust(KEYCARD_SIZE, b"\x00")

    @staticmethod
    def unpack(buf: bytes) -> "Keycard":
        t = KEYCARD_STRUCT.unpack(buf[:KEYCARD_STRUCT.size])
        return Keycard(
            keycard_id=t[0],
            status=t[1],
            room_id=t[2],
            serial=read_str(t[3]),
            created_at=t[4],
            updated_at=t[5],
        )

# ----------------------------- Binary Stores ---------------------------------

class FixedStore:
    """Base class for fixed-length binary records (append/update/soft-delete)."""
    path: str
    size: int
    struct_obj: struct.Struct
    cls: type

    def __init__(self, path: str, size: int):
        self.path = path
        self.size = size
        if not os.path.exists(self.path):
            with open(self.path, "wb") as f:
                pass

    def __len__(self) -> int:
        return os.path.getsize(self.path) // self.size

    def _read_at(self, index: int) -> Optional[bytes]:
        with open(self.path, "rb") as f:
            f.seek(index * self.size)
            b = f.read(self.size)
            return b if len(b) == self.size else None

    def _write_at(self, index: int, data: bytes) -> None:
        assert len(data) == self.size
        with open(self.path, "r+b") as f:
            f.seek(index * self.size)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    def append(self, obj) -> int:
        idx = len(self)
        self._write_at(idx, obj.pack())
        return idx

    def update(self, index: int, obj) -> None:
        self._write_at(index, obj.pack())

    def iter(self) -> Iterable[Tuple[int, object]]:
        total = len(self)
        for i in range(total):
            b = self._read_at(i)
            if not b: 
                continue
            yield i, self.cls.unpack(b)

    # convenience
    def find_first(self, keyfn) -> Optional[Tuple[int, object]]:
        for i, rec in self.iter():
            if keyfn(rec):
                return i, rec
        return None

class RoomStore(FixedStore):
    cls = Room
    def __init__(self, path: str):
        super().__init__(path, ROOM_SIZE)

class GuestStore(FixedStore):
    cls = Guest
    def __init__(self, path: str):
        super().__init__(path, GUEST_SIZE)

class StayStore(FixedStore):
    cls = Stay
    def __init__(self, path: str):
        super().__init__(path, STAY_SIZE)

class KeycardStore(FixedStore):
    cls = Keycard
    def __init__(self, path: str):
        super().__init__(path, KEYCARD_SIZE)

# ----------------------------- Domain Services --------------------------------

class HotelService:
    def __init__(self):
        self.rooms = RoomStore(os.path.join(DATA_DIR, "rooms.dat"))
        self.guests = GuestStore(os.path.join(DATA_DIR, "guests.dat"))
        self.stays = StayStore(os.path.join(DATA_DIR, "stays.dat"))
        self.keycards = KeycardStore(os.path.join(DATA_DIR, "keycards.dat"))

    # ---- Helpers ----
    def _next_id(self, store: FixedStore, attr: str) -> int:
        max_id = 0
        for _, rec in store.iter():
            rid = getattr(rec, attr)
            max_id = max(max_id, rid)
        return max_id + 1

    # ---- CRUD Rooms ----
    def add_room(self, room_type: str, floor: int, capacity: int, max_cards: int) -> Room:
        room = Room(
            room_id=self._next_id(self.rooms, "room_id"),
            status=ROOM_ACTIVE_VACANT,
            room_type=room_type,
            floor=floor,
            capacity=capacity,
            max_cards=max_cards,
            created_at=now_ts(),
            updated_at=now_ts(),
        )
        self.rooms.append(room)
        return room

    def update_room(self, room_id: int, **fields) -> Optional[Room]:
        pos = self.rooms.find_first(lambda r: r.room_id == room_id)
        if not pos: return None
        idx, room = pos
        for k, v in fields.items():
            if hasattr(room, k) and k not in ("room_id", "created_at"):
                setattr(room, k, v)
        room.updated_at = now_ts()
        self.rooms.update(idx, room)
        return room

    def delete_room(self, room_id: int) -> bool:
        pos = self.rooms.find_first(lambda r: r.room_id == room_id)
        if not pos: return False
        idx, room = pos
        room.status = ROOM_DELETED
        room.updated_at = now_ts()
        self.rooms.update(idx, room)
        return True

    # ---- CRUD Guests ----
    def add_guest(self, full_name: str, phone: str, id_no: str) -> Guest:
        guest = Guest(
            guest_id=self._next_id(self.guests, "guest_id"),
            status=GUEST_ACTIVE,
            full_name=full_name,
            phone=phone,
            id_no=id_no,
            created_at=now_ts(),
            updated_at=now_ts(),
        )
        self.guests.append(guest)
        return guest

    def update_guest(self, guest_id: int, **fields) -> Optional[Guest]:
        pos = self.guests.find_first(lambda g: g.guest_id == guest_id)
        if not pos: return None
        idx, g = pos
        for k, v in fields.items():
            if hasattr(g, k) and k not in ("guest_id", "created_at"):
                setattr(g, k, v)
        g.updated_at = now_ts()
        self.guests.update(idx, g)
        return g

    def delete_guest(self, guest_id: int) -> bool:
        pos = self.guests.find_first(lambda g: g.guest_id == guest_id)
        if not pos: return False
        idx, g = pos
        g.status = GUEST_DELETED
        g.updated_at = now_ts()
        self.guests.update(idx, g)
        return True

    # ---- Stays (Check-in / Check-out simplified under View->Summary usage) ----
    def checkin(self, guest_id: int, room_id: int, date_str: str, cards_issued: int) -> Optional[Stay]:
        # validate
        rp = self.rooms.find_first(lambda r: r.room_id == room_id and r.status in (ROOM_ACTIVE_VACANT, ROOM_ACTIVE_OCCUPIED))
        gp = self.guests.find_first(lambda g: g.guest_id == guest_id and g.status == GUEST_ACTIVE)
        if not rp or not gp:
            return None
        r_idx, room = rp
        if room.status == ROOM_ACTIVE_OCCUPIED:
            return None
        if cards_issued < 0 or cards_issued > room.max_cards:
            return None

        stay = Stay(
            stay_id=self._next_id(self.stays, "stay_id"),
            status=STAY_OPEN,
            guest_id=guest_id,
            room_id=room_id,
            checkin_date=date_str,
            checkout_date="",
            cards_issued=cards_issued,
            cards_returned=0,
            updated_at=now_ts(),
        )
        self.stays.append(stay)
        
        # Create keycard records for the issued cards
        for i in range(cards_issued):
            serial = f"KC{room_id:03d}{guest_id:03d}{now_ts() % 10000:04d}{i+1:02d}"
            self.add_keycard(room_id, serial)
        
        room.status = ROOM_ACTIVE_OCCUPIED
        room.updated_at = now_ts()
        self.rooms.update(r_idx, room)
        return stay

    def checkout(self, stay_id: int, date_str: str) -> bool:
        pos = self.stays.find_first(lambda s: s.stay_id == stay_id and s.status == STAY_OPEN)
        if not pos: return False
        idx, st = pos
        st.status = STAY_CLOSED
        st.checkout_date = date_str
        st.cards_returned = max(st.cards_returned, st.cards_issued)
        st.updated_at = now_ts()
        self.stays.update(idx, st)
        
        # Mark keycards as returned (soft delete)
        room_keycards = self.get_keycards_by_room(st.room_id)
        for keycard in room_keycards:
            if keycard.status == KEYCARD_ACTIVE:
                self.delete_keycard(keycard.keycard_id)
        
        # free room
        rp = self.rooms.find_first(lambda r: r.room_id == st.room_id)
        if rp:
            r_idx, room = rp
            if room.status != ROOM_DELETED:
                room.status = ROOM_ACTIVE_VACANT
                room.updated_at = now_ts()
                self.rooms.update(r_idx, room)
        return True

    def delete_stay(self, stay_id: int) -> bool:
        pos = self.stays.find_first(lambda s: s.stay_id == stay_id)
        if not pos: return False
        idx, st = pos
        st.status = STAY_DELETED
        st.updated_at = now_ts()
        self.stays.update(idx, st)
        return True

    # ---- CRUD Keycards ----
    def add_keycard(self, room_id: int, serial: str) -> Keycard:
        keycard = Keycard(
            keycard_id=self._next_id(self.keycards, "keycard_id"),
            status=KEYCARD_ACTIVE,
            room_id=room_id,
            serial=serial,
            created_at=now_ts(),
            updated_at=now_ts(),
        )
        self.keycards.append(keycard)
        return keycard

    def update_keycard(self, keycard_id: int, **fields) -> Optional[Keycard]:
        pos = self.keycards.find_first(lambda k: k.keycard_id == keycard_id)
        if not pos: return None
        idx, k = pos
        for key, val in fields.items():
            if hasattr(k, key) and key not in ("keycard_id", "created_at"):
                setattr(k, key, val)
        k.updated_at = now_ts()
        self.keycards.update(idx, k)
        return k

    def delete_keycard(self, keycard_id: int) -> bool:
        pos = self.keycards.find_first(lambda k: k.keycard_id == keycard_id)
        if not pos: return False
        idx, k = pos
        k.status = KEYCARD_DELETED
        k.updated_at = now_ts()
        self.keycards.update(idx, k)
        return True

    def get_keycards(self, include_deleted=False) -> List[Keycard]:
        res = []
        for _, k in self.keycards.iter():
            if include_deleted or k.status != KEYCARD_DELETED:
                res.append(k)
        return res

    def get_keycards_by_room(self, room_id: int) -> List[Keycard]:
        return [k for k in self.get_keycards() if k.room_id == room_id]

    # ---- Queries for View/Report ----
    def get_rooms(self, include_deleted=False) -> List[Room]:
        res = []
        for _, r in self.rooms.iter():
            if include_deleted or r.status != ROOM_DELETED:
                res.append(r)
        return res

    def get_guests(self, include_deleted=False) -> List[Guest]:
        res = []
        for _, g in self.guests.iter():
            if include_deleted or g.status != GUEST_DELETED:
                res.append(g)
        return res

    def get_stays(self, include_deleted=False) -> List[Stay]:
        res = []
        for _, s in self.stays.iter():
            if include_deleted or s.status != STAY_DELETED:
                res.append(s)
        return res

# ----------------------------- Reporting --------------------------------------

class Report:
    APP_VERSION = "1.0"
    ENDIAN = "Little-Endian"
    ENCODING = "UTF-8 (fixed-length)"

    def __init__(self, svc: HotelService):
        self.svc = svc

    def _line(self, ch: str = "-", width: int = 100) -> str:
        return ch * width

    def _rooms_table(self, rooms: List[Room]) -> str:
        # columns with guest info, phone, ID, and keycard serials
        cols = ["RoomID","Type","Floor","Capacity","MaxCards","Status","Guest","Phone","ID Number","Keycard Serials","Check-in"]
        widths = [8,10,7,9,9,10,25,15,15,20,12]
        def row(vals):
            return " | ".join(str(v).ljust(w) for v,w in zip(vals, widths))
        header = " | ".join(c.ljust(w) for c,w in zip(cols, widths))
        # Calculate line length to match actual table width
        line = "-" * len(header)
        out = [header, line]
        
        # Get active stays for guest info
        stays = {s.room_id: s for s in self.svc.get_stays() if s.status == STAY_OPEN}
        # Get guests for name lookup
        guests = {g.guest_id: g for g in self.svc.get_guests()}
        # Get keycards for serial lookup
        keycards = {k.room_id: [kc for kc in self.svc.get_keycards() if kc.room_id == k.room_id] for k in self.svc.get_keycards()}
        
        for r in rooms:
            status = "Deleted" if r.status==ROOM_DELETED else ("Occupied" if r.status==ROOM_ACTIVE_OCCUPIED else "Active")
            # Get guest info if room is occupied
            guest_name = "-"
            guest_phone = "-"
            guest_id = "-"
            keycard_serials = "-"
            checkin_date = "-"
            if r.status == ROOM_ACTIVE_OCCUPIED and r.room_id in stays:
                stay = stays[r.room_id]
                if stay.guest_id in guests:
                    guest = guests[stay.guest_id]
                    guest_name = guest.full_name
                    guest_phone = guest.phone
                    guest_id = guest.id_no
                    checkin_date = stay.checkin_date
                    # Get keycard serials for this room
                    if r.room_id in keycards:
                        keycard_serials = ", ".join([k.serial for k in keycards[r.room_id]])
            
            out.append(row([
                r.room_id, r.room_type, r.floor, r.capacity, 
                r.max_cards, status, guest_name, guest_phone, guest_id, keycard_serials, checkin_date
            ]))
        return "\n".join(out)

    def _summary(self, rooms: List[Room], stays: List[Stay]) -> str:
        total = len(rooms)
        active = sum(1 for r in rooms if r.status != ROOM_DELETED)
        deleted = sum(1 for r in rooms if r.status == ROOM_DELETED)
        occupied = sum(1 for r in rooms if r.status == ROOM_ACTIVE_OCCUPIED)
        vacant = sum(1 for r in rooms if r.status == ROOM_ACTIVE_VACANT)
        open_stays = sum(1 for s in stays if s.status == STAY_OPEN)
        return dedent(f"""
        Summary (เฉพาะห้องสถานะ Active)
        - Total Rooms (records) : {total}
        - Active Rooms          : {active}
        - Deleted Rooms         : {deleted}
        - Currently Occupied    : {occupied}
        - Available Now         : {vacant}
        - Open Stays            : {open_stays}
        """).strip()

    def _stats_by_type(self, rooms: List[Room]) -> str:
        from collections import Counter
        c = Counter(r.room_type for r in rooms if r.status != ROOM_DELETED)
        lines = ["Rooms by Type (Active only)"]
        for k, v in sorted(c.items()):
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def build_text(self) -> str:
        rooms = self.svc.get_rooms(include_deleted=True)
        stays = self.svc.get_stays(include_deleted=True)

        header = dedent(f"""\
        Hotel Key Card System — Summary Report
        Generated At : {datetime.now().strftime("%Y-%m-%d %H:%M")} (+07:00)
        App Version  : {self.APP_VERSION}
        Endianness   : {self.ENDIAN}
        Encoding     : {self.ENCODING}
        """).rstrip()

        table = self._rooms_table(rooms)
        summary = self._summary(rooms, stays)
        bytype = self._stats_by_type(rooms)

        bigline = self._line("-", 95)
        return "\n".join([header, "", bigline, table, bigline, "", summary, "", bytype]).rstrip()

    def save(self, path: str) -> str:
        txt = self.build_text()
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        return path

# ----------------------------- CLI --------------------------------------------

class CLI:
    def __init__(self, svc: HotelService):
        self.svc = svc

    def input_int(self, prompt: str, default: Optional[int]=None) -> int:
        while True:
            s = input(prompt + (f" [{default}]" if default is not None else "") + ": ").strip()
            if not s and default is not None:
                return default
            if s.isdigit():
                return int(s)
            print("Please enter a valid number")

    def main_menu(self):
        while True:
            print("\n=== Hotel Key Card CLI ===")
            print("1) Add\n2) Update\n3) Delete\n4) View\n0) Exit")
            choice = input("Select : ").strip()
            if choice == "1":
                self.menu_add()
            elif choice == "2":
                self.menu_update()
            elif choice == "3":
                self.menu_delete()
            elif choice == "4":
                self.menu_view()
            elif choice == "0":
                print("Goodbye!")
                return
            else:
                print("Invalid menu option")

    # ----------------- Add -----------------
    def menu_add(self):
        print("\nAdd: 1) Room  2) Guest  3) Stay(Check-in)  4) Keycard")
        c = input("Select: ").strip()
        if c == "1":
            # Show existing rooms
            print("\n=== Existing Rooms ===")
            rooms = self.svc.get_rooms(include_deleted=False)
            if rooms:
                headers = ["ID", "ประเภท", "ชั้น", "ความจุ", "จำนวนคีย์การ์ด", "สถานะ"]
                rows = [self._format_room_row(r) for r in rooms]
                print(self._format_table(headers, rows))
            else:
                print("No rooms in the system yet")
            
            print("\n=== Add New Room ===")
            rt = input("Room Type (STD/DELUXE/SUITE/..): ").strip()[:20]
            if not rt:
                print("Return to main menu")
                return
            floor = self.input_int("Floor")
            cap = self.input_int("Capacity")
            mx = self.input_int("Max keycards")
            room = self.svc.add_room(rt, floor, cap, mx)
            print(f"Room added: {room}")
            
        elif c == "2":
            # Show existing guests
            print("\n=== Existing Guests ===")
            guests = self.svc.get_guests(include_deleted=False)
            if guests:
                headers = ["ID", "Full Name", "Phone", "ID Number", "Status"]
                rows = [self._format_guest_row(g) for g in guests]
                print(self._format_table(headers, rows))
            else:
                print("No guests in the system yet")
            
            print("\n=== Add New Guest ===")
            name = input("Full name: ").strip()[:50]
            if not name:
                print("Return to main menu")
                return
            phone = input("Phone: ").strip()[:15]
            idno = input("ID/Passport: ").strip()[:20]
            g = self.svc.add_guest(name, phone, idno)
            print(f"Guest added: {g}")
            
        elif c == "3":
            # Show available rooms and active guests
            print("\n=== Available Rooms ===")
            available_rooms = [r for r in self.svc.get_rooms(include_deleted=False) 
                             if r.status == ROOM_ACTIVE_VACANT]
            if available_rooms:
                headers = ["ID", "Type", "Floor", "Capacity", "Max Cards"]
                rows = [[str(r.room_id), r.room_type, str(r.floor), 
                        str(r.capacity), str(r.max_cards)] for r in available_rooms]
                print(self._format_table(headers, rows))
            else:
                print("No vacant rooms available")
                return
            
            print("\n=== Active Guests ===")
            active_guests = self.svc.get_guests(include_deleted=False)
            if active_guests:
                headers = ["ID", "Full Name", "Phone", "ID Number"]
                rows = [[str(g.guest_id), g.full_name, g.phone, g.id_no] 
                       for g in active_guests]
                print(self._format_table(headers, rows))
            else:
                print("No guests in the system")
                return
            
            print("\n=== Perform Check-in ===")
            gid = self.input_int("Guest ID")
            rid = self.input_int("Room ID")
            
            # Validate selected room and guest exist
            selected_room = next((r for r in available_rooms if r.room_id == rid), None)
            selected_guest = next((g for g in active_guests if g.guest_id == gid), None)
            
            if not selected_room:
                print("Selected room not found or not available")
                return
            if not selected_guest:
                print("Selected guest not found")
                return
            
            print(f"\nCheck-in Information:")
            print(f"Room: {selected_room.room_type} (Room {selected_room.room_id}) - Floor {selected_room.floor}")
            print(f"Guest: {selected_guest.full_name}")
            print(f"Maximum key cards: {selected_room.max_cards}")
            
            date = input("Check-in date (YYYY-MM-DD) [today]: ").strip() or datetime.now().strftime("%Y-%m-%d")
            cards = self.input_int(f"Cards to issue (1-{selected_room.max_cards})", 1)
            
            st = self.svc.checkin(gid, rid, date, cards)
            if st:
                print(f"Check-in successful: StayID={st.stay_id}")
                print(f"Room {rid} status changed to 'Occupied'")
                # Show issued keycard serials
                room_keycards = self.svc.get_keycards_by_room(rid)
                if room_keycards:
                    print(f"Issued keycard serials: {', '.join([k.serial for k in room_keycards])}")
            else:
                print("Check-in failed (verify Guest/Room/Status/MaxCards)")
                
        elif c == "4":
            # Add new keycard
            print("\n=== Add New Keycard ===")
            # Show existing rooms
            rooms = self.svc.get_rooms(include_deleted=False)
            if rooms:
                headers = ["ID", "Type", "Floor", "Capacity", "Max Cards", "Status"]
                rows = [self._format_room_row(r) for r in rooms]
                print(self._format_table(headers, rows))
            else:
                print("No rooms in the system yet")
                return
                
            room_id = self.input_int("Room ID")
            serial = input("Serial Number: ").strip()[:10]
            if not serial:
                print("Serial number is required")
                return
            keycard = self.svc.add_keycard(room_id, serial)
            print(f"Keycard added: {keycard}")
        else:
            print("Return to main menu")

    # ----------------- Update -----------------
    def menu_update(self):
        print("\nUpdate: 1) Room  2) Guest  3) Stay(Check-out)  4) Keycard")
        c = input("Select: ").strip()
        if c == "1":
            # Show all rooms
            print("\nAll Rooms:")
            print("ID | Type | Floor | Capacity | Max Cards | Status")
            print("-" * 70)
            rooms = self.svc.get_rooms(include_deleted=False)
            for r in rooms:
                status = "Vacant" if r.status == ROOM_ACTIVE_VACANT else "Occupied" if r.status == ROOM_ACTIVE_OCCUPIED else "Deleted"
                print(f"{r.room_id} | {r.room_type} | {r.floor} | {r.capacity} | {r.max_cards} | {status}")
            print("-" * 70)

            # Get room ID to edit
            rid = self.input_int("\nSelect Room ID to edit")
            
            # Find current room data
            current = self.svc.rooms.find_first(lambda r: r.room_id == rid)
            if not current:
                print("Room not found")
                return

            # Show current data
            _, room = current
            print(f"\nCurrent Information:")
            print(f"Room Type: {room.room_type}")
            print(f"Floor: {room.floor}")
            print(f"Capacity: {room.capacity}")
            print(f"Max Key Cards: {room.max_cards}")

            print("\nEnter new information (leave blank to keep current):")
            rt = input("Room Type: ").strip() or room.room_type
            floor = input("Floor: ").strip()
            cap = input("Capacity: ").strip()
            mx = input("Max Key Cards: ").strip()

            fields = {
                "room_type": rt[:20],
                "floor": int(floor) if floor.isdigit() else room.floor,
                "capacity": int(cap) if cap.isdigit() else room.capacity,
                "max_cards": int(mx) if mx.isdigit() else room.max_cards
            }

            upd = self.svc.update_room(rid, **fields)
            if upd:
                print("\nData updated successfully")
                print(f"New information: {upd}")
            else:
                print("Error updating data")

        elif c == "2":
            # Show all guests
            print("\nAll Guests:")
            print("ID | Full Name | Phone | ID/Passport")
            print("-" * 70)
            guests = self.svc.get_guests(include_deleted=False)
            for g in guests:
                print(f"{g.guest_id} | {g.full_name} | {g.phone} | {g.id_no}")
            print("-" * 70)
            
            # Get guest ID to edit
            gid = self.input_int("\nSelect Guest ID to edit")
            
            # Find current guest data
            current = self.svc.guests.find_first(lambda g: g.guest_id == gid)
            if not current:
                print("Guest not found")
                return
                
            # Show current data
            _, guest = current
            print(f"\nCurrent Information:")
            print(f"Full Name: {guest.full_name}")
            print(f"Phone: {guest.phone}")
            print(f"ID/Passport: {guest.id_no}")
            
            print("\nEnter new information (leave blank to keep current):")
            name = input("Full Name: ").strip() or guest.full_name
            phone = input("Phone: ").strip() or guest.phone
            idno = input("ID/Passport: ").strip() or guest.id_no
            
            # Update data
            fields = {
                "full_name": name[:50],
                "phone": phone[:15],
                "id_no": idno[:20]
            }
            
            upd = self.svc.update_guest(gid, **fields)
            if upd:
                print("\nData updated successfully")
                print(f"New information: {upd}")
            else:
                print("Error updating data")

        elif c == "3":
            # Show stays that haven't checked out yet
            print("\nStays not yet checked out:")
            print("Stay ID | Room | Guest | Phone | ID Number | Keycard Serials | Check-in Date")
            print("-" * 120)
            
            stays = [s for s in self.svc.get_stays() if s.status == STAY_OPEN]
            guests = {g.guest_id: g for g in self.svc.get_guests()}
            rooms = {r.room_id: r for r in self.svc.get_rooms()}
            
            for s in stays:
                guest_name = guests[s.guest_id].full_name if s.guest_id in guests else "Unknown"
                guest_phone = guests[s.guest_id].phone if s.guest_id in guests else "N/A"
                guest_id = guests[s.guest_id].id_no if s.guest_id in guests else "N/A"
                room_type = rooms[s.room_id].room_type if s.room_id in rooms else "Unknown"
                # Get keycard serials for this room
                room_keycards = self.svc.get_keycards_by_room(s.room_id)
                keycard_serials = ", ".join([k.serial for k in room_keycards]) if room_keycards else "N/A"
                print(f"{s.stay_id} | {room_type} (Room {s.room_id}) | {guest_name} | {guest_phone} | {guest_id} | {keycard_serials} | {s.checkin_date}")
            print("-" * 120)

            # Get ID for check-out
            sid = self.input_int("\nSelect Stay ID for check-out")
            
            # Find the desired stay
            current = self.svc.stays.find_first(lambda s: s.stay_id == sid and s.status == STAY_OPEN)
            if not current:
                print("Stay not found or already checked out")
                return

            # Show information and confirm check-out
            _, stay = current
            guest_name = guests[stay.guest_id].full_name if stay.guest_id in guests else "Unknown"
            room_type = rooms[stay.room_id].room_type if stay.room_id in rooms else "Unknown"
            
            print(f"\nStay Information:")
            print(f"Room: {room_type} (Room {stay.room_id})")
            print(f"Guest: {guest_name}")
            print(f"Phone: {guests[stay.guest_id].phone if stay.guest_id in guests else 'N/A'}")
            print(f"ID Number: {guests[stay.guest_id].id_no if stay.guest_id in guests else 'N/A'}")
            print(f"Check-in date: {stay.checkin_date}")
            # Show keycard serials
            room_keycards = self.svc.get_keycards_by_room(stay.room_id)
            if room_keycards:
                print(f"Keycard serials: {', '.join([k.serial for k in room_keycards])}")
            
            confirm = input("\nConfirm check-out (y/N): ").strip().lower()
            if confirm != 'y':
                print("Check-out cancelled")
                return

            date = input("Check-out date (YYYY-MM-DD) [today]: ").strip() or datetime.now().strftime("%Y-%m-%d")
            if self.svc.checkout(sid, date):
                print(f"\nCheck-out successful")
                print(f"Check-out date: {date}")
            else:
                print("Error during check-out")

        elif c == "4":
            # Update keycard
            print("\n=== Update Keycard ===")
            # Show all keycards
            keycards = self.svc.get_keycards()
            if keycards:
                headers = ["Keycard ID", "Room ID", "Serial", "Status"]
                rows = []
                for k in keycards:
                    status = "Active" if k.status == KEYCARD_ACTIVE else "Deleted"
                    rows.append([str(k.keycard_id), str(k.room_id), k.serial, status])
                print(self._format_table(headers, rows))
            else:
                print("No keycards in the system")
                return
                
            keycard_id = self.input_int("Keycard ID to update")
            current = self.svc.keycards.find_first(lambda k: k.keycard_id == keycard_id)
            if not current:
                print("Keycard not found")
                return
            _, keycard = current
            print(f"\nCurrent Information:")
            print(f"Room ID: {keycard.room_id}")
            print(f"Serial: {keycard.serial}")
            
            print("\nEnter new information (leave blank to keep current):")
            new_room = input("New Room ID: ").strip()
            new_serial = input("New Serial: ").strip()
            fields = {}
            if new_room.isdigit():
                fields["room_id"] = int(new_room)
            if new_serial:
                fields["serial"] = new_serial[:10]
            if fields:
                updated = self.svc.update_keycard(keycard_id, **fields)
                if updated:
                    print("Keycard updated successfully")
                else:
                    print("Error updating keycard")
            else:
                print("No changes made")
        else:
            print("Return to main menu")

    # ----------------- Delete -----------------
    def menu_delete(self):
        print("\nDelete (soft): 1) Room  2) Guest  3) Stay  4) Keycard")
        c = input("Select: ").strip()
        if c == "1":
            rid = self.input_int("Room ID")
            ok = self.svc.delete_room(rid)
            print("Deleted" if ok else "Room not found")
        elif c == "2":
            gid = self.input_int("Guest ID")
            ok = self.svc.delete_guest(gid)
            print("Deleted" if ok else "Guest not found")
        elif c == "3":
            sid = self.input_int("Stay ID")
            ok = self.svc.delete_stay(sid)
            print("Deleted" if ok else "Stay not found")
        elif c == "4":
            # Show all keycards first
            keycards = self.svc.get_keycards()
            if keycards:
                headers = ["Keycard ID", "Room ID", "Serial", "Status"]
                rows = []
                for k in keycards:
                    status = "Active" if k.status == KEYCARD_ACTIVE else "Deleted"
                    rows.append([str(k.keycard_id), str(k.room_id), k.serial, status])
                print("\nAll Keycards:")
                print(self._format_table(headers, rows))
            else:
                print("No keycards in the system")
                return
                
            keycard_id = self.input_int("Keycard ID to delete")
            ok = self.svc.delete_keycard(keycard_id)
            print("Deleted" if ok else "Keycard not found")
        else:
            print("Return to main menu")

    # ----------------- View -----------------
    def _format_table(self, headers: List[str], rows: List[List[str]], widths: Optional[List[int]] = None) -> str:
        if not widths:
            # Calculate column widths based on content
            widths = []
            for i in range(len(headers)):
                col_items = [str(row[i]) for row in rows] + [headers[i]]
                widths.append(max(len(item) for item in col_items) + 2)
        
        # Create header
        header = " | ".join(str(h).ljust(w) for h, w in zip(headers, widths))
        separator = "-" * (sum(widths) + 3 * (len(widths) - 1))
        
        # Create rows
        formatted_rows = [
            " | ".join(str(cell).ljust(w) for cell, w in zip(row, widths))
            for row in rows
        ]
        
        return "\n".join([header, separator] + formatted_rows)

    def _format_room_row(self, room: Room) -> List[str]:
        status = "Vacant" if room.status == ROOM_ACTIVE_VACANT else "Occupied" if room.status == ROOM_ACTIVE_OCCUPIED else "Deleted"
        return [
            str(room.room_id),
            room.room_type,
            str(room.floor),
            str(room.capacity),
            str(room.max_cards),
            status
        ]

    def _format_guest_row(self, guest: Guest) -> List[str]:
        return [
            str(guest.guest_id),
            guest.full_name,
            guest.phone,
            guest.id_no,
            "Active" if guest.status == GUEST_ACTIVE else "Deleted"
        ]

    def _format_stay_row(self, stay: Stay, guests: Dict[int, Guest], rooms: Dict[int, Room]) -> List[str]:
        guest = guests.get(stay.guest_id, None)
        room = rooms.get(stay.room_id, None)
        status = "Open" if stay.status == STAY_OPEN else "Closed" if stay.status == STAY_CLOSED else "Deleted"
        return [
            str(stay.stay_id),
            str(stay.room_id),
            room.room_type if room else "N/A",
            guest.full_name if guest else "N/A",
            stay.checkin_date,
            stay.checkout_date or "-",
            str(stay.cards_issued),
            str(stay.cards_returned),
            status
        ]

    def menu_view(self):
        print(dedent("""
        View:
          1) View Single Record
          2) View All Records
          3) View Filtered Records
          4) Summary Statistics + Export Report
          5) View Keycards
        """))
        c = input("Select: ").strip()
        if c == "1":
            sub = input("Select: 1) Room  2) Guest  3) Stay : ").strip()
            if sub == "1":
                # Show all rooms first
                print("\nAll Rooms:")
                rooms = self.svc.get_rooms()
                headers = ["ID", "Type", "Floor", "Capacity", "Max Cards", "Status"]
                rows = [self._format_room_row(r) for r in rooms]
                print(self._format_table(headers, rows))
                
                rid = self.input_int("\nSelect Room ID to view")
                pos = self.svc.rooms.find_first(lambda r: r.room_id == rid)
                if pos:
                    _, room = pos
                    print("\nSelected Room Information:")
                    print(self._format_table(headers, [self._format_room_row(room)]))
                else:
                    print("Room not found")
                    
            elif sub == "2":
                # Show all guests
                print("\nAll Guests:")
                guests = self.svc.get_guests()
                headers = ["ID", "Full Name", "Phone", "ID Number", "Status"]
                rows = [self._format_guest_row(g) for g in guests]
                print(self._format_table(headers, rows))
                
                gid = self.input_int("\nSelect Guest ID to view")
                pos = self.svc.guests.find_first(lambda g: g.guest_id == gid)
                if pos:
                    _, guest = pos
                    print("\nSelected Guest Information:")
                    print(self._format_table(headers, [self._format_guest_row(guest)]))
                else:
                    print("Guest not found")
            else:
                # Show all stays
                print("\nAll Stays:")
                stays = self.svc.get_stays()
                guests = {g.guest_id: g for g in self.svc.get_guests()}
                rooms = {r.room_id: r for r in self.svc.get_rooms()}
                
                headers = ["StayID", "RoomID", "Room Type", "Guest Name", "Check-in", "Check-out", "Cards Issued", "Cards Returned", "Status"]
                rows = [self._format_stay_row(s, guests, rooms) for s in stays]
                print(self._format_table(headers, rows))
                
                sid = self.input_int("\nSelect Stay ID to view")
                pos = self.svc.stays.find_first(lambda s: s.stay_id == sid)
                if pos:
                    _, stay = pos
                    print("\nSelected Stay Information:")
                    print(self._format_table(headers, [self._format_stay_row(stay, guests, rooms)]))
                else:
                    print("Stay information not found")
                    
        elif c == "2":
            sub = input("Select: 1) Rooms  2) Guests  3) Stays : ").strip()
            if sub == "1":
                rooms = self.svc.get_rooms()
                headers = ["ID", "Type", "Floor", "Capacity", "Max Cards", "Status"]
                rows = [self._format_room_row(r) for r in rooms]
                print("\nAll Rooms:")
                print(self._format_table(headers, rows))
            elif sub == "2":
                guests = self.svc.get_guests()
                headers = ["ID", "Full Name", "Phone", "ID Number", "Status"]
                rows = [self._format_guest_row(g) for g in guests]
                print("\nAll Guests:")
                print(self._format_table(headers, rows))
            else:
                stays = self.svc.get_stays()
                guests = {g.guest_id: g for g in self.svc.get_guests()}
                rooms = {r.room_id: r for r in self.svc.get_rooms()}
                headers = ["StayID", "RoomID", "Room Type", "Guest Name", "Check-in", "Check-out", "Cards Issued", "Cards Returned", "Status"]
                rows = [self._format_stay_row(s, guests, rooms) for s in stays]
                print("\nAll Stays:")
                print(self._format_table(headers, rows))
        elif c == "3":
            print("Filter Rooms: 1) Vacant Only  2) Occupied Only  3) By Type")
            sub = input("Select: ").strip()
            rooms = self.svc.get_rooms(include_deleted=False)
            if sub == "1":
                rooms = [r for r in rooms if r.status == ROOM_ACTIVE_VACANT]
            elif sub == "2":
                rooms = [r for r in rooms if r.status == ROOM_ACTIVE_OCCUPIED]
            elif sub == "3":
                typ = input("Room Type: ").strip()
                rooms = [r for r in rooms if r.room_type == typ]
            rep = Report(self.svc)
            print(rep._rooms_table(rooms))
        elif c == "4":
            path = os.path.join(REPORT_DIR, "hotel_report.txt")
            rep = Report(self.svc)
            rep.save(path)
            print(f"Export successful → {path}")
            print("\nReport header preview:\n")
            print(rep.build_text().split("\n", 8)[0:8])
        elif c == "5":
            # View keycards
            print("\nKeycard View: 1) All Keycards  2) By Room  3) By Status")
            sub = input("Select: ").strip()
            if sub == "1":
                keycards = self.svc.get_keycards()
                if keycards:
                    headers = ["Keycard ID", "Room ID", "Serial", "Status", "Created"]
                    rows = []
                    for k in keycards:
                        status = "Active" if k.status == KEYCARD_ACTIVE else "Deleted"
                        created = fmt_date(k.created_at)
                        rows.append([str(k.keycard_id), str(k.room_id), k.serial, status, created])
                    print("\nAll Keycards:")
                    print(self._format_table(headers, rows))
                else:
                    print("No keycards in the system")
            elif sub == "2":
                room_id = self.input_int("Room ID")
                room_keycards = self.svc.get_keycards_by_room(room_id)
                if room_keycards:
                    headers = ["Keycard ID", "Serial", "Status", "Created"]
                    rows = []
                    for k in room_keycards:
                        status = "Active" if k.status == KEYCARD_ACTIVE else "Deleted"
                        created = fmt_date(k.created_at)
                        rows.append([str(k.keycard_id), k.serial, status, created])
                    print(f"\nKeycards for Room {room_id}:")
                    print(self._format_table(headers, rows))
                else:
                    print(f"No keycards found for Room {room_id}")
            elif sub == "3":
                status_filter = input("Status (1=Active, 0=Deleted): ").strip()
                if status_filter in ["0", "1"]:
                    status_val = int(status_filter)
                    keycards = [k for k in self.svc.get_keycards() if k.status == status_val]
                    if keycards:
                        headers = ["Keycard ID", "Room ID", "Serial", "Status", "Created"]
                        rows = []
                        for k in keycards:
                            status = "Active" if k.status == KEYCARD_ACTIVE else "Deleted"
                            created = fmt_date(k.created_at)
                            rows.append([str(k.keycard_id), str(k.room_id), k.serial, status, created])
                        print(f"\nKeycards with status {status_val}:")
                        print(self._format_table(headers, rows))
                    else:
                        print(f"No keycards found with status {status_val}")
                else:
                    print("Invalid status filter")
            else:
                print("Return to main menu")
        else:
            print("Return to main menu")

# ----------------------------- Entry Point ------------------------------------

def seed_example_data(svc: HotelService):
    """Insert sample data for testing (call with --seed)"""
    try:
        # Add various room types
        if len(list(svc.rooms.iter())) == 0:
            print("Adding room data...")
            # Standard Rooms
            svc.add_room("STD", 2, 2, 2)
            # Deluxe Room
            svc.add_room("DELUXE", 5, 3, 3)
            # Suite
            svc.add_room("SUITE", 10, 4, 4)
            print("Room data added successfully")

        # Add guest data
        if len(list(svc.guests.iter())) == 0:
            print("Adding guest data...")
            svc.add_guest("John Smith", "0812345678", "A1234567890")
            svc.add_guest("Jane Doe", "0899999999", "B9876543210")
            print("Guest data added successfully")

        # Perform sample check-in
        rooms = svc.get_rooms()
        guests = svc.get_guests()
        if rooms and guests and len(list(svc.stays.iter())) == 0:
            print("Performing sample check-in...")
            # Check-in guest to STD room
            svc.checkin(guests[0].guest_id, rooms[0].room_id, 
                       datetime.now().strftime("%Y-%m-%d"), 1)
            print("Check-in completed successfully")
            
    except Exception as e:
        print(f"Error adding sample data: {str(e)}")
        return False
    
    return True

def main():
    try:
        parser = argparse.ArgumentParser(description="Hotel Key Card CLI (Binary struct / OOP)")
        parser.add_argument("--seed", action="store_true", help="Add sample data")
        args = parser.parse_args()

        svc = HotelService()
        if args.seed:
            if seed_example_data(svc):
                print("\nSample data added successfully")
            else:
                print("\nError adding sample data")
                return

        CLI(svc).main_menu()
    except KeyboardInterrupt:
        print("\nProgram terminated")
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()
