#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotel Key Card CLI — Binary File I/O (struct) / OOP / Standard Library Only
Python 3.10+

Files (fixed-length, little-endian '<'):
  data/rooms.dat   : master rooms
  data/guests.dat  : master guests
  data/stays.dat   : master stays (การเข้าพัก: Guest x Room)

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

# Status constants
ROOM_DELETED = 0
ROOM_ACTIVE_VACANT = 1
ROOM_ACTIVE_OCCUPIED = 2

GUEST_DELETED = 0
GUEST_ACTIVE = 1

STAY_DELETED = 9
STAY_OPEN = 1
STAY_CLOSED = 0

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

# ----------------------------- Domain Services --------------------------------

class HotelService:
    def __init__(self):
        self.rooms = RoomStore(os.path.join(DATA_DIR, "rooms.dat"))
        self.guests = GuestStore(os.path.join(DATA_DIR, "guests.dat"))
        self.stays = StayStore(os.path.join(DATA_DIR, "stays.dat"))

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
        # columns like sample image
        cols = ["RoomID","Type","Floor","Capacity","MaxCards","Status"]
        widths = [8,10,7,9,9,10]
        def row(vals):
            return " | ".join(str(v).ljust(w) for v,w in zip(vals, widths))
        header = " | ".join(c.ljust(w) for c,w in zip(cols, widths))
        line = "-" * (sum(widths) + 3*(len(widths)-1))
        out = [header, line]
        for r in rooms:
            status = "Deleted" if r.status==ROOM_DELETED else ("Occupied" if r.status==ROOM_ACTIVE_OCCUPIED else "Active")
            out.append(row([r.room_id, r.room_type, r.floor, r.capacity, r.max_cards, status]))
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
            print("กรุณากรอกตัวเลขให้ถูกต้อง")

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
                print("เมนูไม่ถูกต้อง")

    # ----------------- Add -----------------
    def menu_add(self):
        print("\nAdd: 1) Room  2) Guest  3) Stay(Check-in)")
        c = input("เลือก: ").strip()
        if c == "1":
            rt = input("Room Type (STD/DELUXE/SUITE/..): ").strip()[:20]
            floor = self.input_int("Floor")
            cap = self.input_int("Capacity")
            mx = self.input_int("Max keycards")
            room = self.svc.add_room(rt, floor, cap, mx)
            print(f"เพิ่มห้องแล้ว: {room}")
        elif c == "2":
            name = input("Full name: ").strip()[:50]
            phone = input("Phone: ").strip()[:15]
            idno = input("ID/Passport: ").strip()[:20]
            g = self.svc.add_guest(name, phone, idno)
            print(f"เพิ่มแขกแล้ว: {g}")
        elif c == "3":
            gid = self.input_int("Guest ID")
            rid = self.input_int("Room ID")
            date = input("Check-in date (YYYY-MM-DD): ").strip() or datetime.now().strftime("%Y-%m-%d")
            cards = self.input_int("Cards to issue (<= room.max_cards)", 1)
            st = self.svc.checkin(gid, rid, date, cards)
            if st:
                print(f"Check-in สำเร็จ: StayID={st.stay_id}")
            else:
                print("Check-in ไม่สำเร็จ (ตรวจสอบ Guest/Room/Status/MaxCards)")
        else:
            print("กลับเมนูหลัก")

    # ----------------- Update -----------------
    def menu_update(self):
        print("\nUpdate: 1) Room  2) Guest  3) Stay(Check-out)")
        c = input("เลือก: ").strip()
        if c == "1":
            rid = self.input_int("Room ID")
            print("ปล่อยว่างถ้าไม่แก้ไขฟิลด์นั้น")
            rt = input("Room Type: ").strip()
            floor = input("Floor: ").strip()
            cap = input("Capacity: ").strip()
            mx = input("Max keycards: ").strip()
            fields = {}
            if rt: fields["room_type"] = rt[:20]
            if floor.isdigit(): fields["floor"] = int(floor)
            if cap.isdigit(): fields["capacity"] = int(cap)
            if mx.isdigit(): fields["max_cards"] = int(mx)
            upd = self.svc.update_room(rid, **fields)
            print("สำเร็จ" if upd else "ไม่พบห้อง")
        elif c == "2":
            gid = self.input_int("Guest ID")
            print("ปล่อยว่างถ้าไม่แก้ไข")
            name = input("Full name: ").strip()
            phone = input("Phone: ").strip()
            idno = input("ID/Passport: ").strip()
            fields = {}
            if name: fields["full_name"] = name[:50]
            if phone: fields["phone"] = phone[:15]
            if idno: fields["id_no"] = idno[:20]
            upd = self.svc.update_guest(gid, **fields)
            print("สำเร็จ" if upd else "ไม่พบแขก")
        elif c == "3":
            sid = self.input_int("Stay ID")
            date = input("Checkout date (YYYY-MM-DD): ").strip() or datetime.now().strftime("%Y-%m-%d")
            ok = self.svc.checkout(sid, date)
            print("Check-out สำเร็จ" if ok else "ไม่พบ Stay แบบเปิดอยู่")
        else:
            print("กลับเมนูหลัก")

    # ----------------- Delete -----------------
    def menu_delete(self):
        print("\nDelete (soft): 1) Room  2) Guest  3) Stay")
        c = input("เลือก: ").strip()
        if c == "1":
            rid = self.input_int("Room ID")
            ok = self.svc.delete_room(rid)
            print("ลบแล้ว" if ok else "ไม่พบห้อง")
        elif c == "2":
            gid = self.input_int("Guest ID")
            ok = self.svc.delete_guest(gid)
            print("ลบแล้ว" if ok else "ไม่พบแขก")
        elif c == "3":
            sid = self.input_int("Stay ID")
            ok = self.svc.delete_stay(sid)
            print("ลบแล้ว" if ok else "ไม่พบ Stay")
        else:
            print("กลับเมนูหลัก")

    # ----------------- View -----------------
    def menu_view(self):
        print(dedent("""
        View:
          1) ดูรายการเดียว
          2) ดูทั้งหมด
          3) ดูแบบกรอง
          4) สถิติโดยสรุป + Export Report
        """))
        c = input("เลือก: ").strip()
        if c == "1":
            sub = input("เลือก: 1) Room  2) Guest  3) Stay : ").strip()
            if sub == "1":
                rid = self.input_int("Room ID")
                pos = self.svc.rooms.find_first(lambda r: r.room_id == rid)
                print(pos[1] if pos else "ไม่พบ")
            elif sub == "2":
                gid = self.input_int("Guest ID")
                pos = self.svc.guests.find_first(lambda g: g.guest_id == gid)
                print(pos[1] if pos else "ไม่พบ")
            else:
                sid = self.input_int("Stay ID")
                pos = self.svc.stays.find_first(lambda s: s.stay_id == sid)
                print(pos[1] if pos else "ไม่พบ")
        elif c == "2":
            sub = input("เลือก: 1) Rooms  2) Guests  3) Stays : ").strip()
            if sub == "1":
                for _, r in self.svc.rooms.iter(): print(r)
            elif sub == "2":
                for _, g in self.svc.guests.iter(): print(g)
            else:
                for _, s in self.svc.stays.iter(): print(s)
        elif c == "3":
            print("กรองห้อง: 1) เฉพาะว่าง  2) เฉพาะไม่ว่าง  3) ตาม Type")
            sub = input("เลือก: ").strip()
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
            print(f"Export เรียบร้อย → {path}")
            print("\nตัวอย่างส่วนหัวรายงาน:\n")
            print(rep.build_text().split("\n", 8)[0:8])
        else:
            print("กลับเมนูหลัก")

# ----------------------------- Entry Point ------------------------------------

def seed_example_data(svc: HotelService):
    """ใส่ข้อมูลตัวอย่างเพื่อทดสอบ (เรียกด้วย --seed)"""
    try:
        # เพิ่มห้องพักหลากหลายประเภท
        if len(list(svc.rooms.iter())) == 0:
            print("กำลังเพิ่มข้อมูลห้องพัก...")
            # Standard Rooms
            svc.add_room("STD", 2, 2, 2)
            # Deluxe Room
            svc.add_room("DELUXE", 5, 3, 3)
            # Suite
            svc.add_room("SUITE", 10, 4, 4)
            print("เพิ่มห้องพักเรียบร้อย")

        # เพิ่มข้อมูลแขก
        if len(list(svc.guests.iter())) == 0:
            print("กำลังเพิ่มข้อมูลแขก...")
            svc.add_guest("John Smith", "0812345678", "A1234567890")
            svc.add_guest("Jane Doe", "0899999999", "B9876543210")
            print("เพิ่มข้อมูลแขกเรียบร้อย")

        # ทำ check-in ตัวอย่าง
        rooms = svc.get_rooms()
        guests = svc.get_guests()
        if rooms and guests and len(list(svc.stays.iter())) == 0:
            print("กำลังทำ check-in ตัวอย่าง...")
            # Check-in guest to STD room
            svc.checkin(guests[0].guest_id, rooms[0].room_id, 
                       datetime.now().strftime("%Y-%m-%d"), 1)
            print("ทำ check-in เรียบร้อย")
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการเพิ่มข้อมูลตัวอย่าง: {str(e)}")
        return False
    
    return True

    # เพิ่มข้อมูลแขก
    if len(list(svc.guests.iter())) == 0:
        svc.add_guest("Alice Wonderland", "0812345678", "A1234567890")
        svc.add_guest("Bob Builder", "0899999999", "B9876543210")
        svc.add_guest("Charlie Chan", "0823456789", "C2345678901")
        svc.add_guest("David Smith", "0834567890", "D3456789012")
        svc.add_guest("Emma Watson", "0845678901", "E4567890123")
        svc.add_guest("Frank Wilson", "0856789012", "F5678901234")

    # ทำ check-in ตัวอย่าง
    rooms = svc.get_rooms()
    guests = svc.get_guests()
    if rooms and guests:
        # Check-in Alice to STD room
        svc.checkin(guests[0].guest_id, rooms[0].room_id, datetime.now().strftime("%Y-%m-%d"), 1)
        # Check-in Bob to DELUXE room
        svc.checkin(guests[1].guest_id, rooms[3].room_id, datetime.now().strftime("%Y-%m-%d"), 2)
        # Check-in Charlie to SUITE
        svc.checkin(guests[2].guest_id, rooms[6].room_id, datetime.now().strftime("%Y-%m-%d"), 3)
        
        # Checkout Bob (to show history)
        stays = svc.get_stays()
        for stay in stays:
            if stay.guest_id == guests[1].guest_id:
                checkout_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                svc.checkout(stay.stay_id, checkout_date)

def main():
    try:
        parser = argparse.ArgumentParser(description="Hotel Key Card CLI (Binary struct / OOP)")
        parser.add_argument("--seed", action="store_true", help="เติมข้อมูลตัวอย่าง")
        args = parser.parse_args()

        svc = HotelService()
        if args.seed:
            if seed_example_data(svc):
                print("\nเพิ่มข้อมูลตัวอย่างเรียบร้อย")
            else:
                print("\nเกิดข้อผิดพลาดในการเพิ่มข้อมูลตัวอย่าง")
                return

        CLI(svc).main_menu()
    except KeyboardInterrupt:
        print("\nจบการทำงาน")
    except Exception as e:
        print(f"\nเกิดข้อผิดพลาด: {str(e)}")
        raise

if __name__ == "__main__":
    main()
