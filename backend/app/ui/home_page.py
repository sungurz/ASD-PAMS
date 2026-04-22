# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/home_page.py
====================
Role-appropriate home dashboard.
Shows key stats, occupancy, finance and activity feed.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from app.db.database import SessionLocal
from app.services.reports_service import get_dashboard_summary, get_recent_activity


class HomePage(tb.Frame):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_dashboard()

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
        # Header
        header = tb.Frame(self, padding=(24, 20, 24, 8))
        header.pack(fill=X)

        role_display = self.user.role_value.replace("_", " ").title()
        city_display = f" — {self.user.city_name}" if hasattr(self.user, "city_name") and self.user.city_name else ""

        tb.Label(header, text=f"Welcome, {self.user.full_name or self.user.username}",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)
        tb.Label(header, text=f"{role_display}{city_display}",
                 font=("Helvetica", 11), bootstyle="secondary").pack(side=LEFT, padx=(12, 0))

        tb.Button(header, text="↻  Refresh", bootstyle="secondary",
                  padding=(8, 4), command=self.load_dashboard).pack(side=RIGHT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=24, pady=(0, 0))

        # Scrollable content
        self._content = tb.Frame(self, padding=(24, 16, 24, 16))
        self._content.pack(fill=BOTH, expand=YES)

    def load_dashboard(self):
        self._refresh_db()
        # Clear existing content
        for w in self._content.winfo_children():
            w.destroy()

        city_id = getattr(self.user, "city_id", None)

        try:
            data     = get_dashboard_summary(self.db, city_id=city_id)
            activity = get_recent_activity(self.db, city_id=city_id)
        except Exception as e:
            tb.Label(self._content, text=f"Could not load dashboard: {e}",
                     bootstyle="danger").pack(pady=20)
            return

        occ  = data["occupancy"]
        fin  = data["finance"]
        maint = data["maintenance"]
        comp  = data["complaints"]

        # ── Occupancy row ──────────────────────────────────────────────────
        self._section_label("Occupancy")
        occ_row = tb.Frame(self._content)
        occ_row.pack(fill=X, pady=(6, 16))

        self._stat_card(occ_row, f"{occ['occupancy_rate']}%",    "Occupancy Rate",  "success")
        self._stat_card(occ_row, str(occ['occupied']),           "Occupied Units",  "primary")
        self._stat_card(occ_row, str(occ['available']),          "Available Units", "info")
        self._stat_card(occ_row, str(occ['maintenance']),        "In Maintenance",  "warning")

        # ── Finance row (only if permitted) ───────────────────────────────
        if self.user.has_permission("invoice.view") or self.user.has_permission("report.finance"):
            self._section_label("Finance")
            fin_row = tb.Frame(self._content)
            fin_row.pack(fill=X, pady=(6, 16))

            self._stat_card(fin_row, f"£{fin['this_month']:,.0f}",    "This Month",     "success")
            self._stat_card(fin_row, f"£{fin['total_collected']:,.0f}", "Total Collected","primary")
            self._stat_card(fin_row, f"£{fin['outstanding']:,.0f}",   "Outstanding",    "warning")
            self._stat_card(fin_row, f"£{fin['overdue']:,.0f}",       "Overdue",        "danger")

        # ── Maintenance & Complaints row ───────────────────────────────────
        if self.user.has_permission("maintenance.view") or self.user.has_permission("complaint.view"):
            self._section_label("Operations")
            ops_row = tb.Frame(self._content)
            ops_row.pack(fill=X, pady=(6, 16))

            if self.user.has_permission("maintenance.view"):
                self._stat_card(ops_row, str(maint['open']),        "Open Tickets",   "warning")
                self._stat_card(ops_row, str(maint['urgent_open']), "Urgent Tickets", "danger")

            if self.user.has_permission("complaint.view"):
                self._stat_card(ops_row, str(comp['open']),         "Open Complaints","danger")
                self._stat_card(ops_row, str(comp['under_review']), "Under Review",   "warning")

        # ── Activity feed ──────────────────────────────────────────────────
        if activity:
            self._section_label("Recent Activity")
            feed = tb.Frame(self._content)
            feed.pack(fill=X, pady=(6, 0))

            TYPE_COLORS = {
                "maintenance": "warning",
                "complaint":   "danger",
                "invoice":     "info",
            }

            for event in activity:
                color = TYPE_COLORS.get(event["type"], "secondary")
                card = tb.Frame(feed, padding=(12, 8))
                card.pack(fill=X, pady=(0, 4))

                left_bar = tb.Frame(card, width=3, bootstyle=color)
                left_bar.pack(side=LEFT, fill=Y, padx=(0, 12))
                left_bar.pack_propagate(False)

                text_frame = tb.Frame(card)
                text_frame.pack(side=LEFT, fill=X, expand=YES)
                tb.Label(text_frame, text=event["text"],
                         font=("Helvetica", 11, "bold")).pack(anchor=W)
                tb.Label(text_frame, text=event["sub"],
                         font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

                if event.get("date"):
                    tb.Label(card, text=event["date"].strftime("%d %b %Y"),
                             font=("Helvetica", 10), bootstyle="secondary").pack(side=RIGHT)

    def _section_label(self, text: str):
        row = tb.Frame(self._content)
        row.pack(fill=X, pady=(12, 0))
        tb.Label(row, text=text,
                 font=("Georgia", 13, "bold")).pack(side=LEFT)
        tb.Separator(row, orient=HORIZONTAL).pack(side=LEFT, fill=X, expand=YES, padx=(12, 0))

    def _stat_card(self, parent, value: str, label: str, style: str):
        # Outer wrapper with subtle border
        outer = tb.Frame(parent, padding=1)
        outer.pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))

        card = tb.Frame(outer, padding=(16, 14))
        card.pack(fill=BOTH, expand=YES)

        tb.Label(card, text=value,
                 font=("Georgia", 24, "bold"), bootstyle=style).pack(anchor=W)
        tb.Label(card, text=label,
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(2, 0))