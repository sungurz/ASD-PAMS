# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/reports_page.py
=======================
Reports page with three tabs:
  - Occupancy report
  - Finance report
  - Maintenance report
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from app.db.database import SessionLocal
from app.services.reports_service import (
    get_occupancy_by_city, get_occupancy_summary,
    get_finance_summary, get_monthly_revenue,
    get_maintenance_summary, get_open_tickets_by_status,
    get_complaints_summary, get_maintenance_costs,
)


class ReportsPage(tb.Frame):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_reports()

    def destroy(self):
        try:
            self.db.close()
        except Exception:
            pass
        super().destroy()

    def _refresh_db(self):
        try:
            self.db.close()
        except Exception:
            pass
        from app.db.database import SessionLocal as _SL
        self.db = _SL()

    def _build_ui(self):
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)
        tb.Label(header, text="Reports",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)
        tb.Button(header, text="↻  Refresh", bootstyle="secondary",
                  padding=(8, 4), command=self.load_reports).pack(side=RIGHT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        self.nb = tb.Notebook(self, bootstyle="primary")
        self.nb.pack(fill=BOTH, expand=YES, padx=20, pady=12)

        self._tab_occ   = tb.Frame(self.nb, padding=16)
        self._tab_fin   = tb.Frame(self.nb, padding=16)
        self._tab_maint = tb.Frame(self.nb, padding=16)

        self.nb.add(self._tab_occ,   text="  Occupancy  ")
        if self.user.has_permission("report.finance"):
            self.nb.add(self._tab_fin, text="  Finance  ")
        self.nb.add(self._tab_maint, text="  Maintenance  ")

    def load_reports(self):
        self._refresh_db()
        self._load_occupancy()
        if self.user.has_permission("report.finance"):
            self._load_finance()
        self._load_maintenance()

    # ── Occupancy ──────────────────────────────────────────────────────────
    def _load_occupancy(self):
        for w in self._tab_occ.winfo_children():
            w.destroy()

        city_id = getattr(self.user, "city_id", None)

        # Summary cards
        summary = get_occupancy_summary(self.db, city_id=city_id)
        cards_frame = tb.Frame(self._tab_occ)
        cards_frame.pack(fill=X, pady=(0, 20))

        self._card(cards_frame, f"{summary['occupancy_rate']}%", "Occupancy Rate", "success")
        self._card(cards_frame, str(summary['occupied']),        "Occupied",       "primary")
        self._card(cards_frame, str(summary['available']),       "Available",      "info")
        self._card(cards_frame, str(summary['maintenance']),     "Maintenance",    "warning")

        # Per-city breakdown (manager only)
        if not city_id and self.user.has_permission("report.crosscity"):
            tb.Label(self._tab_occ, text="Breakdown by City",
                     font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

            cols = ("city", "total", "occupied", "available", "maintenance", "rate")
            tree = tb.Treeview(self._tab_occ, columns=cols, show="headings",
                               bootstyle="dark", height=6)
            col_cfg = [
                ("city",        "City",         120, W),
                ("total",       "Total Units",  90,  CENTER),
                ("occupied",    "Occupied",     90,  CENTER),
                ("available",   "Available",    90,  CENTER),
                ("maintenance", "Maintenance",  100, CENTER),
                ("rate",        "Rate %",       80,  CENTER),
            ]
            for cid, heading, width, anchor in col_cfg:
                tree.heading(cid, text=heading, anchor=anchor)
                tree.column(cid, width=width, anchor=anchor)

            for row in get_occupancy_by_city(self.db):
                tree.insert("", END, values=(
                    row["city"], row["total"], row["occupied"],
                    row["available"], row["maintenance"],
                    f"{row['occupancy_rate']}%",
                ))
            tree.pack(fill=X)

    # ── Finance ────────────────────────────────────────────────────────────
    def _load_finance(self):
        for w in self._tab_fin.winfo_children():
            w.destroy()

        city_id = getattr(self.user, "city_id", None)
        fin = get_finance_summary(self.db, city_id=city_id)

        cards = tb.Frame(self._tab_fin)
        cards.pack(fill=X, pady=(0, 20))
        self._card(cards, f"£{fin['this_month']:,.0f}",     "This Month",      "success")
        self._card(cards, f"£{fin['total_collected']:,.0f}", "Total Collected", "primary")
        self._card(cards, f"£{fin['outstanding']:,.0f}",    "Outstanding",     "warning")
        self._card(cards, f"£{fin['overdue']:,.0f}",        "Overdue",         "danger")

        # Monthly revenue table
        tb.Label(self._tab_fin, text="Monthly Revenue (last 6 months)",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

        monthly = get_monthly_revenue(self.db, city_id=city_id, months=6)
        if monthly:
            cols = ("month", "amount")
            tree = tb.Treeview(self._tab_fin, columns=cols, show="headings",
                               bootstyle="dark", height=len(monthly))
            tree.heading("month",  text="Month",    anchor=W)
            tree.heading("amount", text="Collected", anchor=CENTER)
            tree.column("month",  width=160, anchor=W)
            tree.column("amount", width=140, anchor=CENTER)
            for row in reversed(monthly):
                tree.insert("", END, values=(row["month"], f"£{row['amount']:,.2f}"))
            tree.pack(fill=X)
        else:
            tb.Label(self._tab_fin, text="No payment data yet.",
                     bootstyle="secondary").pack(anchor=W)

    # ── Maintenance ────────────────────────────────────────────────────────
    def _load_maintenance(self):
        for w in self._tab_maint.winfo_children():
            w.destroy()

        city_id = getattr(self.user, "city_id", None)
        maint = get_maintenance_summary(self.db, city_id=city_id)
        comp  = get_complaints_summary(self.db, city_id=city_id)

        tb.Label(self._tab_maint, text="Maintenance Tickets",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

        cards = tb.Frame(self._tab_maint)
        cards.pack(fill=X, pady=(0, 20))
        self._card(cards, str(maint['open']),        "Open Tickets",  "warning")
        self._card(cards, str(maint['urgent_open']), "Urgent",        "danger")
        self._card(cards, str(maint['resolved']),    "Resolved",      "success")
        self._card(cards, str(maint['total']),       "Total",         "secondary")

        # Maintenance costs for budget management
        costs = get_maintenance_costs(self.db, city_id=city_id)
        tb.Label(self._tab_maint, text="Maintenance Costs",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

        cost_cards = tb.Frame(self._tab_maint)
        cost_cards.pack(fill=X, pady=(0, 12))
        self._card(cost_cards, f"£{costs['total_material_cost']:,.2f}", "Total Material Cost", "danger")
        self._card(cost_cards, f"{costs['total_hours']}h",              "Total Hours Spent",   "warning")
        self._card(cost_cards, str(costs['resolved_count']),            "Jobs Completed",      "success")

        if costs['top_cost_tickets']:
            tb.Label(self._tab_maint, text="Most Expensive Jobs",
                     font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))
            cols = ("title", "cost", "hours")
            tree_c = tb.Treeview(self._tab_maint, columns=cols, show="headings",
                                 bootstyle="dark", height=len(costs['top_cost_tickets']))
            tree_c.heading("title", text="Ticket",        anchor=W)
            tree_c.heading("cost",  text="Material Cost", anchor=CENTER)
            tree_c.heading("hours", text="Hours Spent",   anchor=CENTER)
            tree_c.column("title", width=280, anchor=W)
            tree_c.column("cost",  width=120, anchor=CENTER)
            tree_c.column("hours", width=100, anchor=CENTER)
            for t in costs['top_cost_tickets']:
                tree_c.insert("", END, values=(
                    t["title"], f"£{t['cost']:,.2f}",
                    f"{t['hours']}h" if t['hours'] else "—"
                ))
            tree_c.pack(fill=X, pady=(0, 20))

        # By status breakdown
        tb.Label(self._tab_maint, text="Open Tickets by Status",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

        by_status = get_open_tickets_by_status(self.db, city_id=city_id)
        if by_status:
            cols = ("status", "count")
            tree = tb.Treeview(self._tab_maint, columns=cols, show="headings",
                               bootstyle="dark", height=len(by_status))
            tree.heading("status", text="Status", anchor=W)
            tree.heading("count",  text="Count",  anchor=CENTER)
            tree.column("status", width=200, anchor=W)
            tree.column("count",  width=80,  anchor=CENTER)
            for row in by_status:
                tree.insert("", END, values=(row["status"], row["count"]))
            tree.pack(fill=X, pady=(0, 20))

        # Complaints summary
        tb.Label(self._tab_maint, text="Complaints",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

        cards2 = tb.Frame(self._tab_maint)
        cards2.pack(fill=X)
        self._card(cards2, str(comp['open']),         "Open",         "danger")
        self._card(cards2, str(comp['under_review']), "Under Review", "warning")
        self._card(cards2, str(comp['resolved']),     "Resolved",     "success")
        self._card(cards2, str(comp['total']),        "Total",        "secondary")

    # ── Helpers ────────────────────────────────────────────────────────────
    def _card(self, parent, value: str, label: str, style: str):
        outer = tb.Frame(parent, padding=1)
        outer.pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))
        card = tb.Frame(outer, padding=(16, 12))
        card.pack(fill=BOTH, expand=YES)
        tb.Label(card, text=value,
                 font=("Georgia", 20, "bold"), bootstyle=style).pack(anchor=W)
        tb.Label(card, text=label,
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(2, 0))