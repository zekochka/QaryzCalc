from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from qaryzcalc.calculations import (
    add_months,
    calculate,
    calculate_down_payment_amount,
    calculate_down_payment_percent,
    calculate_mortgage_loan_amount,
)
from qaryzcalc.exporters import export_schedule_to_csv
from qaryzcalc.formatters import format_date, format_money, format_percent, format_ratio, parse_decimal
from qaryzcalc.models import CalculationInput, CalculationResult, EarlyPayment

ctk.set_default_color_theme("blue")


def run() -> None:
    app = QaryzCalcApp()
    app.mainloop()


class ToolTip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.window is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.window = ctk.CTkToplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(
            self.window,
            text=self.text,
            justify="left",
            wraplength=280,
            fg_color=("white", "#1d2430"),
            text_color=("black", "white"),
            corner_radius=12,
            padx=12,
            pady=8,
        )
        label.pack()

    def hide(self, _event=None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class EarlyPaymentDialog(ctk.CTkToplevel):
    def __init__(self, master, payment: EarlyPayment | None, on_save) -> None:
        super().__init__(master)
        self.title("Досрочное погашение")
        self.geometry("440x250")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.on_save = on_save

        self.date_var = ctk.StringVar(value=format_date(payment.payment_date) if payment else "")
        self.amount_var = ctk.StringVar(value=self._amount_to_text(payment.amount) if payment else "")
        self.recalc_var = ctk.StringVar(
            value=self._recalc_label(payment.recalc_type) if payment else "Уменьшить срок"
        )

        frame = ctk.CTkFrame(self, corner_radius=20)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Дата", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(16, 8), sticky="w"
        )
        ctk.CTkEntry(frame, textvariable=self.date_var).grid(row=0, column=1, padx=12, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(frame, text="Сумма", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=1, column=0, padx=12, pady=8, sticky="w"
        )
        ctk.CTkEntry(frame, textvariable=self.amount_var).grid(row=1, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(frame, text="Пересчёт", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=2, column=0, padx=12, pady=8, sticky="w"
        )
        ctk.CTkSegmentedButton(
            frame,
            values=["Уменьшить срок", "Уменьшить платёж"],
            variable=self.recalc_var,
            command=self._sync_hint,
        ).grid(row=2, column=1, padx=12, pady=8, sticky="ew")

        self.hint_label = ctk.CTkLabel(frame, text="", justify="left", wraplength=280)
        self.hint_label.grid(row=3, column=0, columnspan=2, padx=12, pady=(4, 12), sticky="w")
        self._sync_hint(self.recalc_var.get())

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(buttons, text="Отмена", fg_color="transparent", border_width=1, command=self.destroy).grid(
            row=0, column=0, padx=(0, 8), sticky="ew"
        )
        ctk.CTkButton(buttons, text="Сохранить", command=self._save).grid(row=0, column=1, sticky="ew")

    @staticmethod
    def _amount_to_text(value: Decimal) -> str:
        raw = f"{value:.2f}"
        integer, _, fraction = raw.partition(".")
        return integer if fraction == "00" else raw.replace(".", ",")

    @staticmethod
    def _recalc_label(value: str) -> str:
        return "Уменьшить срок" if value == "reduce_term" else "Уменьшить платёж"

    def _sync_hint(self, value: str) -> None:
        text = (
            "После платежа программа постарается сократить срок кредита."
            if value == "Уменьшить срок"
            else "После платежа программа пересчитает будущий ежемесячный платёж."
        )
        self.hint_label.configure(text=text)

    def _save(self) -> None:
        try:
            payment_date = datetime.strptime(self.date_var.get().strip(), "%d.%m.%Y").date()
            amount = parse_decimal(self.amount_var.get(), "Сумма досрочного погашения")
            if amount <= Decimal("0"):
                raise ValueError("Сумма досрочного погашения должна быть больше нуля.")
        except ValueError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return

        recalc_type = "reduce_term" if self.recalc_var.get() == "Уменьшить срок" else "reduce_payment"
        self.on_save(EarlyPayment(payment_date=payment_date, amount=amount, recalc_type=recalc_type))
        self.destroy()


class QaryzCalcApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QaryzCalc")
        self.geometry("1480x960")
        self.minsize(1260, 760)

        ctk.set_appearance_mode("light")
        self.current_theme = "light"
        self.result: CalculationResult | None = None
        self.early_payments: list[EarlyPayment] = []
        self.metric_labels: dict[str, ctk.CTkLabel] = {}
        self.chart_canvases: list[FigureCanvasTkAgg] = []
        self.sync_lock = False

        self.mode_var = ctk.StringVar(value="Ипотека")
        self.payment_type_var = ctk.StringVar(value="Аннуитетный")
        self.term_unit_var = ctk.StringVar(value="Годы")
        self.status_var = ctk.StringVar(value="Заполните параметры и нажмите «Рассчитать».")

        self.loan_amount_var = ctk.StringVar()
        self.annual_rate_var = ctk.StringVar()
        self.term_value_var = ctk.StringVar()
        self.issue_date_var = ctk.StringVar()
        self.first_payment_date_var = ctk.StringVar()
        self.one_time_commission_var = ctk.StringVar(value="0")
        self.monthly_commission_var = ctk.StringVar(value="0")
        self.insurance_cost_var = ctk.StringVar(value="0")
        self.apr_rate_var = ctk.StringVar(value="")
        self.property_price_var = ctk.StringVar()
        self.down_payment_amount_var = ctk.StringVar()
        self.down_payment_percent_var = ctk.StringVar()

        self._build_ui()
        self._configure_treeview_style()
        self._bind_events()
        self._load_demo_data()
        self._render_early_payments()
        self._set_results_placeholder()
        self._set_explanation("")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0, height=88)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="QaryzCalc", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=0, padx=(24, 12), pady=18, sticky="w"
        )
        ctk.CTkLabel(
            header,
            text="Калькулятор кредита и ипотеки с наглядным графиком и досрочными платежами",
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=1, pady=18, sticky="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, padx=24, pady=18, sticky="e")
        ctk.CTkSegmentedButton(
            controls,
            values=["Кредит", "Ипотека"],
            variable=self.mode_var,
            command=lambda _value: self._on_mode_changed(),
        ).grid(row=0, column=0, padx=(0, 12))
        ctk.CTkButton(controls, text="Переключить тему", command=self._toggle_theme).grid(row=0, column=1)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=18)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkScrollableFrame(content, width=430, corner_radius=24)
        self.left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 18))

        self.right_panel = ctk.CTkFrame(content, corner_radius=24)
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self._build_form()
        self._build_results()

    def _build_form(self) -> None:
        self.left_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.left_panel,
            text="Параметры кредита",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=8, pady=(10, 16), sticky="w")

        self.core_section = self._create_section(self.left_panel, 1, "Основные данные")
        self.loan_entry = self._add_entry_row(
            self.core_section,
            0,
            "Сумма кредита",
            self.loan_amount_var,
            "Сколько денег вы берёте у банка.",
        )
        self._add_entry_row(
            self.core_section,
            1,
            "Номинальная ставка",
            self.annual_rate_var,
            "Эта ставка используется для расчёта графика платежей.",
        )
        self._add_entry_row(
            self.core_section,
            2,
            "ГЭСВ",
            self.apr_rate_var,
            "Показатель для сравнения предложений банков. На сам график он не влияет.",
        )
        self._add_entry_row(self.core_section, 3, "Срок", self.term_value_var, "Можно выбрать годы или месяцы.")
        ctk.CTkSegmentedButton(
            self.core_section,
            values=["Годы", "Месяцы"],
            variable=self.term_unit_var,
        ).grid(row=4, column=3, padx=(0, 12), pady=8, sticky="e")
        self._add_entry_row(
            self.core_section,
            4,
            "Дата получения",
            self.issue_date_var,
            "Дата, когда банк выдал кредит.",
        )
        self._add_entry_row(
            self.core_section,
            5,
            "Первый платёж",
            self.first_payment_date_var,
            "Эта дата определяет первый месяц в графике.",
        )

        payment_section = self._create_section(self.left_panel, 2, "Тип погашения")
        payment_section.grid_columnconfigure(0, weight=1)
        ctk.CTkSegmentedButton(
            payment_section,
            values=["Аннуитетный", "Дифференцированный"],
            variable=self.payment_type_var,
        ).grid(row=1, column=0, padx=12, pady=(12, 14), sticky="ew")

        self.mortgage_section = self._create_section(self.left_panel, 3, "Параметры ипотеки")
        self._add_entry_row(
            self.mortgage_section,
            0,
            "Стоимость квартиры",
            self.property_price_var,
            "Полная стоимость недвижимости.",
        )
        self._add_entry_row(
            self.mortgage_section,
            1,
            "Первоначальный взнос",
            self.down_payment_amount_var,
            "Сколько вы вносите своими деньгами.",
        )
        self._add_entry_row(
            self.mortgage_section,
            2,
            "Первоначальный взнос, %",
            self.down_payment_percent_var,
            "Если меняете процент, сумма взноса пересчитается автоматически.",
        )

        costs_section = self._create_section(self.left_panel, 4, "Комиссии и расходы")
        self._add_entry_row(
            costs_section,
            0,
            "Единовременная комиссия",
            self.one_time_commission_var,
            "Разовый расход при оформлении кредита.",
        )
        self._add_entry_row(
            costs_section,
            1,
            "Ежемесячная комиссия",
            self.monthly_commission_var,
            "Добавляется к каждому платежу в графике.",
        )
        self._add_entry_row(
            costs_section,
            2,
            "Страховка",
            self.insurance_cost_var,
            "Дополнительный расход. В график банка не входит, но учитывается в общей стоимости.",
        )

        early_section = self._create_section(self.left_panel, 5, "Досрочное погашение")
        early_section.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            early_section,
            text="Добавить досрочный платёж",
            command=self._open_add_early_payment_dialog,
        ).grid(row=1, column=0, padx=12, pady=(12, 8), sticky="ew")

        self.early_payments_container = ctk.CTkFrame(early_section, fg_color="transparent")
        self.early_payments_container.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.early_payments_container.grid_columnconfigure(0, weight=1)

        actions = self._create_section(self.left_panel, 6, "Действия")
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="Рассчитать", height=42, command=self._calculate).grid(
            row=1, column=0, padx=(12, 6), pady=(12, 10), sticky="ew"
        )
        ctk.CTkButton(actions, text="Очистить", height=42, command=self._clear_form).grid(
            row=1, column=1, padx=(6, 12), pady=(12, 10), sticky="ew"
        )
        self.export_button = ctk.CTkButton(actions, text="Экспортировать CSV", height=42, command=self._export_csv)
        self.export_button.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="ew")
        self.export_button.configure(state="disabled")

        notice = ctk.CTkLabel(
            self.left_panel,
            text=(
                "Расчёт является ориентировочным. Реальный график банка может отличаться "
                "из-за метода подсчёта дней, комиссий, страховок, даты выдачи и условий договора."
            ),
            justify="left",
            wraplength=360,
            fg_color=("#fff8d9", "#3f3612"),
            corner_radius=16,
            padx=14,
            pady=12,
        )
        notice.grid(row=7, column=0, padx=8, pady=(0, 16), sticky="ew")

    def _build_results(self) -> None:
        header = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Результат расчёта", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(header, textvariable=self.status_var, justify="right", wraplength=460).grid(
            row=0, column=1, sticky="e"
        )

        self.tabs = ctk.CTkTabview(self.right_panel, corner_radius=20)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.overview_tab = self.tabs.add("Итоги")
        self.schedule_tab = self.tabs.add("График платежей")
        self.charts_tab = self.tabs.add("Графики")
        self.explanation_tab = self.tabs.add("Как это рассчитано")

        self.overview_tab.grid_columnconfigure((0, 1, 2), weight=1)
        self.schedule_tab.grid_columnconfigure(0, weight=1)
        self.schedule_tab.grid_rowconfigure(0, weight=1)
        self.charts_tab.grid_columnconfigure((0, 1), weight=1)
        self.explanation_tab.grid_columnconfigure(0, weight=1)
        self.explanation_tab.grid_rowconfigure(0, weight=1)

        self._build_metric_cards()
        self._build_schedule_table()
        self._build_chart_frames()

        self.explanation_box = ctk.CTkTextbox(self.explanation_tab, wrap="word")
        self.explanation_box.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.explanation_box.configure(state="disabled")

    def _build_metric_cards(self) -> None:
        card_specs = [
            ("monthly_payment", "Ежемесячный платёж"),
            ("loan_amount", "Сумма кредита"),
            ("total_paid", "Всего банку"),
            ("overpayment", "Общая переплата"),
            ("interest", "Проценты"),
            ("fees", "Комиссии и страховка"),
            ("down_payment", "Первоначальный взнос"),
            ("property_cost", "Полная стоимость объекта"),
            ("last_payment", "Дата последнего платежа"),
            ("payments_count", "Количество платежей"),
            ("interest_saved", "Экономия процентов"),
            ("ratio", "Возврат на 1 тенге"),
        ]

        for index, (key, title) in enumerate(card_specs):
            row, column = divmod(index, 3)
            card = ctk.CTkFrame(self.overview_tab, corner_radius=20)
            card.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=16, pady=(16, 6))
            value_label = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=22, weight="bold"), justify="left")
            value_label.pack(anchor="w", padx=16, pady=(0, 16))
            self.metric_labels[key] = value_label

    def _build_schedule_table(self) -> None:
        frame = ctk.CTkFrame(self.schedule_tab, corner_radius=18)
        frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        columns = (
            "number",
            "date",
            "balance_before",
            "payment",
            "interest",
            "principal",
            "commission",
            "extra",
            "balance_after",
        )
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", style="Qaryz.Treeview")
        headings = {
            "number": "№",
            "date": "Дата",
            "balance_before": "Остаток до",
            "payment": "Платёж",
            "interest": "Проценты",
            "principal": "Основной долг",
            "commission": "Комиссии",
            "extra": "Досрочно",
            "balance_after": "Остаток после",
        }
        widths = {
            "number": 52,
            "date": 100,
            "balance_before": 140,
            "payment": 132,
            "interest": 112,
            "principal": 142,
            "commission": 112,
            "extra": 112,
            "balance_after": 140,
        }

        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center")

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def _build_chart_frames(self) -> None:
        self.balance_chart_frame = ctk.CTkFrame(self.charts_tab, corner_radius=18)
        self.balance_chart_frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self.composition_chart_frame = ctk.CTkFrame(self.charts_tab, corner_radius=18)
        self.composition_chart_frame.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

    def _create_section(self, parent, row: int, title: str) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=20)
        section.grid(row=row, column=0, padx=8, pady=(0, 14), sticky="ew")
        section.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(section, text=title, font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=4, padx=12, pady=(12, 6), sticky="w"
        )
        return section

    def _add_entry_row(self, parent, row: int, label: str, variable, tooltip: str):
        ctk.CTkLabel(parent, text=label).grid(row=row + 1, column=0, padx=(12, 6), pady=8, sticky="w")
        info_button = ctk.CTkButton(parent, text="?", width=28, height=28, corner_radius=14, command=lambda: None)
        info_button.grid(row=row + 1, column=1, padx=(0, 6), pady=8, sticky="w")
        ToolTip(info_button, tooltip)
        entry = ctk.CTkEntry(parent, textvariable=variable)
        entry.grid(row=row + 1, column=2, padx=(6, 12), pady=8, sticky="ew")
        return entry

    def _bind_events(self) -> None:
        for variable in (self.property_price_var, self.down_payment_amount_var):
            variable.trace_add("write", lambda *_args: self._sync_mortgage_fields("amount"))
        self.down_payment_percent_var.trace_add("write", lambda *_args: self._sync_mortgage_fields("percent"))

    def _load_demo_data(self) -> None:
        today = date.today()
        issue = date(today.year, today.month, min(today.day, 28))
        first_payment = add_months(issue, 1)

        self.mode_var.set("Ипотека")
        self.payment_type_var.set("Аннуитетный")
        self.term_unit_var.set("Годы")
        self.property_price_var.set("20 000 000")
        self.down_payment_percent_var.set("20")
        self.down_payment_amount_var.set("4 000 000")
        self.loan_amount_var.set("16 000 000")
        self.annual_rate_var.set("10")
        self.term_value_var.set("15")
        self.issue_date_var.set(format_date(issue))
        self.first_payment_date_var.set(format_date(first_payment))
        self.one_time_commission_var.set("0")
        self.monthly_commission_var.set("0")
        self.insurance_cost_var.set("0")
        self.apr_rate_var.set("")
        self.early_payments = []
        self._on_mode_changed()

    def _clear_form(self) -> None:
        today = date.today()
        issue = date(today.year, today.month, min(today.day, 28))
        first_payment = add_months(issue, 1)

        self.mode_var.set("Кредит")
        self.payment_type_var.set("Аннуитетный")
        self.term_unit_var.set("Месяцы")
        self.loan_amount_var.set("")
        self.annual_rate_var.set("")
        self.term_value_var.set("")
        self.issue_date_var.set(format_date(issue))
        self.first_payment_date_var.set(format_date(first_payment))
        self.one_time_commission_var.set("0")
        self.monthly_commission_var.set("0")
        self.insurance_cost_var.set("0")
        self.apr_rate_var.set("")
        self.property_price_var.set("")
        self.down_payment_amount_var.set("")
        self.down_payment_percent_var.set("")
        self.early_payments = []
        self.result = None
        self.status_var.set("Форма очищена. Можно ввести новые условия кредита.")
        self.export_button.configure(state="disabled")
        self._render_early_payments()
        self._set_results_placeholder()
        self._clear_table()
        self._clear_charts()
        self._set_explanation("")
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        if self._current_mode() == "mortgage":
            self.mortgage_section.grid()
            self.loan_entry.configure(state="disabled")
            self._sync_mortgage_fields("amount")
        else:
            self.mortgage_section.grid_remove()
            self.loan_entry.configure(state="normal")

    def _toggle_theme(self) -> None:
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        ctk.set_appearance_mode(self.current_theme)
        self._configure_treeview_style()
        if self.result is not None:
            self._render_charts(self.result)

    def _configure_treeview_style(self) -> None:
        style = ttk.Style()
        style.theme_use("default")

        if self.current_theme == "light":
            background = "#ffffff"
            foreground = "#102030"
            heading = "#eef3f8"
            selected = "#d9ebff"
        else:
            background = "#1f2630"
            foreground = "#f4f7fb"
            heading = "#2d3745"
            selected = "#35506f"

        style.configure(
            "Qaryz.Treeview",
            background=background,
            foreground=foreground,
            rowheight=28,
            fieldbackground=background,
            borderwidth=0,
        )
        style.configure("Qaryz.Treeview.Heading", background=heading, foreground=foreground, relief="flat")
        style.map("Qaryz.Treeview", background=[("selected", selected)], foreground=[("selected", foreground)])

    def _sync_mortgage_fields(self, source: str) -> None:
        if self.sync_lock or self._current_mode() != "mortgage":
            return

        property_price = self._try_parse_decimal(self.property_price_var.get())
        if property_price is None or property_price <= Decimal("0"):
            return

        self.sync_lock = True
        try:
            if source == "percent":
                percent = self._try_parse_decimal(self.down_payment_percent_var.get())
                if percent is not None:
                    amount = calculate_down_payment_amount(property_price, percent)
                    self.down_payment_amount_var.set(self._amount_to_input(amount))
            else:
                amount = self._try_parse_decimal(self.down_payment_amount_var.get())
                if amount is not None:
                    percent = calculate_down_payment_percent(property_price, amount)
                    self.down_payment_percent_var.set(self._decimal_to_input(percent))
                else:
                    percent = self._try_parse_decimal(self.down_payment_percent_var.get())
                    if percent is not None:
                        amount = calculate_down_payment_amount(property_price, percent)
                        self.down_payment_amount_var.set(self._amount_to_input(amount))

            amount = self._try_parse_decimal(self.down_payment_amount_var.get())
            if amount is not None:
                loan_amount = calculate_mortgage_loan_amount(property_price, amount)
                self.loan_amount_var.set(self._amount_to_input(loan_amount))
        finally:
            self.sync_lock = False

    def _open_add_early_payment_dialog(self) -> None:
        EarlyPaymentDialog(self, None, self._add_early_payment)

    def _add_early_payment(self, payment: EarlyPayment) -> None:
        self.early_payments.append(payment)
        self.early_payments.sort(key=lambda item: item.payment_date)
        self._render_early_payments()

    def _edit_early_payment(self, index: int) -> None:
        current = self.early_payments[index]

        def on_save(updated: EarlyPayment) -> None:
            self.early_payments[index] = updated
            self.early_payments.sort(key=lambda item: item.payment_date)
            self._render_early_payments()

        EarlyPaymentDialog(self, current, on_save)

    def _delete_early_payment(self, index: int) -> None:
        del self.early_payments[index]
        self._render_early_payments()

    def _render_early_payments(self) -> None:
        for child in self.early_payments_container.winfo_children():
            child.destroy()

        if not self.early_payments:
            ctk.CTkLabel(
                self.early_payments_container,
                text="Пока нет досрочных платежей. Их можно добавить в любой момент.",
                justify="left",
                wraplength=320,
            ).grid(row=0, column=0, sticky="w", pady=(4, 0))
            return

        for index, payment in enumerate(self.early_payments):
            card = ctk.CTkFrame(self.early_payments_container, corner_radius=16)
            card.grid(row=index, column=0, sticky="ew", pady=6)
            card.grid_columnconfigure(0, weight=1)
            recalc_label = "уменьшить срок" if payment.recalc_type == "reduce_term" else "уменьшить платёж"
            ctk.CTkLabel(
                card,
                text=f"{format_date(payment.payment_date)}  •  {format_money(payment.amount)}",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
            ctk.CTkLabel(card, text=f"Пересчёт: {recalc_label}").grid(
                row=1, column=0, padx=12, pady=(0, 10), sticky="w"
            )
            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.grid(row=0, column=1, rowspan=2, padx=10, pady=8, sticky="e")
            ctk.CTkButton(buttons, text="Изменить", width=86, command=lambda i=index: self._edit_early_payment(i)).pack(
                padx=4, pady=(0, 6)
            )
            ctk.CTkButton(
                buttons,
                text="Удалить",
                width=86,
                fg_color="#b83535",
                hover_color="#982929",
                command=lambda i=index: self._delete_early_payment(i),
            ).pack(padx=4)

    def _calculate(self) -> None:
        try:
            payload = self._collect_input()
            self.result = calculate(payload)
        except ValueError as exc:
            self.status_var.set("Есть ошибки во входных данных. Исправьте их и повторите расчёт.")
            messagebox.showerror("Ошибка расчёта", str(exc), parent=self)
            return
        except Exception as exc:  # pragma: no cover
            self.status_var.set("Возникла непредвиденная ошибка при расчёте.")
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return

        self.export_button.configure(state="normal")
        self.status_var.set(
            f"Рассчитано {self.result.summary.payment_count} платежей до {format_date(self.result.summary.last_payment_date)}."
        )
        self._fill_metrics(self.result)
        self._fill_table(self.result)
        self._render_charts(self.result)
        self._set_explanation(self._build_explanation(self.result))

    def _collect_input(self) -> CalculationInput:
        mode = self._current_mode()
        issue_date = self._parse_date(self.issue_date_var.get(), "Дата получения")
        first_payment_date = self._parse_date(self.first_payment_date_var.get(), "Первый платёж")
        term_value = self._parse_int(self.term_value_var.get(), "Срок")
        annual_rate = self._parse_required_decimal(self.annual_rate_var.get(), "Номинальная ставка")
        loan_amount = self._parse_required_decimal(self.loan_amount_var.get(), "Сумма кредита")

        apr_text = self.apr_rate_var.get().strip()
        apr_rate = parse_decimal(apr_text, "ГЭСВ") if apr_text else None

        property_price = None
        down_payment_amount = Decimal("0")
        down_payment_percent = Decimal("0")
        if mode == "mortgage":
            property_price = self._parse_required_decimal(self.property_price_var.get(), "Стоимость квартиры")
            down_payment_amount = self._parse_required_decimal(
                self.down_payment_amount_var.get(), "Первоначальный взнос"
            )
            down_payment_percent = self._parse_required_decimal(
                self.down_payment_percent_var.get(), "Первоначальный взнос, %"
            )

        return CalculationInput(
            mode=mode,
            loan_amount=loan_amount,
            annual_rate=annual_rate,
            term_value=term_value,
            term_unit=self._current_term_unit(),
            issue_date=issue_date,
            first_payment_date=first_payment_date,
            payment_type=self._current_payment_type(),
            one_time_commission=parse_decimal(self.one_time_commission_var.get(), "Единовременная комиссия"),
            monthly_commission=parse_decimal(self.monthly_commission_var.get(), "Ежемесячная комиссия"),
            insurance_cost=parse_decimal(self.insurance_cost_var.get(), "Страховка"),
            apr_rate=apr_rate,
            property_price=property_price,
            down_payment_amount=down_payment_amount,
            down_payment_percent=down_payment_percent,
            early_payments=list(self.early_payments),
        )

    def _fill_metrics(self, result: CalculationResult) -> None:
        summary = result.summary
        payment_delta = summary.monthly_payment_max - summary.monthly_payment_min
        monthly_payment = format_money(summary.monthly_payment_max)
        if payment_delta >= Decimal("1.00"):
            monthly_payment = f"от {format_money(summary.monthly_payment_min)} до {format_money(summary.monthly_payment_max)}"

        values = {
            "monthly_payment": monthly_payment,
            "loan_amount": format_money(summary.loan_amount),
            "total_paid": format_money(summary.total_paid_to_bank),
            "overpayment": format_money(summary.total_overpayment),
            "interest": format_money(summary.total_interest),
            "fees": format_money(summary.total_commissions + summary.total_insurance),
            "down_payment": format_money(summary.down_payment_amount)
            if result.input_data.mode == "mortgage"
            else "Не используется",
            "property_cost": format_money(summary.full_property_cost)
            if result.input_data.mode == "mortgage"
            else "Не используется",
            "last_payment": format_date(summary.last_payment_date),
            "payments_count": str(summary.payment_count),
            "interest_saved": format_money(summary.interest_saved),
            "ratio": f"1 ₸ → {format_ratio(summary.effective_ratio)} ₸",
        }

        for key, label in self.metric_labels.items():
            label.configure(text=values[key])

    def _fill_table(self, result: CalculationResult) -> None:
        self._clear_table()
        for row in result.schedule:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.payment_number,
                    format_date(row.payment_date),
                    self._table_money(row.balance_before),
                    self._table_money(row.regular_payment),
                    self._table_money(row.interest),
                    self._table_money(row.principal_paid),
                    self._table_money(row.commission),
                    self._table_money(row.extra_payment),
                    self._table_money(row.balance_after),
                ),
            )

    def _render_charts(self, result: CalculationResult) -> None:
        self._clear_charts()
        text_color = "#1c2430" if self.current_theme == "light" else "#f3f4f6"
        background = "#ffffff" if self.current_theme == "light" else "#202833"
        grid_color = "#d6dee8" if self.current_theme == "light" else "#384252"

        numbers = [row.payment_number for row in result.schedule]
        balances = [float(row.balance_after) for row in result.schedule]
        principals = [float(row.principal_paid) for row in result.schedule]
        interests = [float(row.interest) for row in result.schedule]

        fig1 = Figure(figsize=(5.8, 3.8), dpi=100, facecolor=background)
        ax1 = fig1.add_subplot(111)
        ax1.plot(numbers, balances, color="#0f9d8a", linewidth=2.4)
        ax1.fill_between(numbers, balances, color="#89ddd1", alpha=0.35)
        ax1.set_title("Уменьшение остатка долга", color=text_color, fontsize=14)
        ax1.set_xlabel("Платёж", color=text_color)
        ax1.set_ylabel("Остаток", color=text_color)
        ax1.tick_params(colors=text_color)
        ax1.grid(color=grid_color, alpha=0.5)
        ax1.set_facecolor(background)
        for spine in ax1.spines.values():
            spine.set_color(grid_color)

        canvas1 = FigureCanvasTkAgg(fig1, master=self.balance_chart_frame)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)
        self.chart_canvases.append(canvas1)

        fig2 = Figure(figsize=(5.8, 3.8), dpi=100, facecolor=background)
        ax2 = fig2.add_subplot(111)
        ax2.bar(numbers, principals, label="Основной долг", color="#2d7ff9")
        ax2.bar(numbers, interests, bottom=principals, label="Проценты", color="#f9735b")
        ax2.set_title("Состав платежей", color=text_color, fontsize=14)
        ax2.set_xlabel("Платёж", color=text_color)
        ax2.set_ylabel("Сумма", color=text_color)
        ax2.tick_params(colors=text_color)
        ax2.grid(axis="y", color=grid_color, alpha=0.5)
        legend = ax2.legend(facecolor=background, edgecolor=grid_color)
        for text in legend.get_texts():
            text.set_color(text_color)
        ax2.set_facecolor(background)
        for spine in ax2.spines.values():
            spine.set_color(grid_color)

        canvas2 = FigureCanvasTkAgg(fig2, master=self.composition_chart_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)
        self.chart_canvases.append(canvas2)

    def _clear_charts(self) -> None:
        for canvas in self.chart_canvases:
            canvas.get_tk_widget().destroy()
        self.chart_canvases.clear()

    def _build_explanation(self, result: CalculationResult) -> str:
        summary = result.summary
        first = summary.first_payment
        payment_type_text = "аннуитетный" if result.input_data.payment_type == "annuity" else "дифференцированный"
        apr_line = (
            f"ГЭСВ для справки: {format_percent(result.input_data.apr_rate)}.\n"
            if result.input_data.apr_rate is not None
            else ""
        )

        return (
            "Как работает расчёт\n\n"
            "Новый остаток = старый остаток + начисленные проценты - платёж - досрочное погашение.\n\n"
            f"Сейчас выбран {payment_type_text} способ погашения. "
            "Для графика используется именно номинальная ставка, а ГЭСВ оставлена как справочное поле.\n"
            f"{apr_line}\n"
            "Формулы\n"
            "Аннуитет: A = P × r / (1 - (1 + r)^(-n))\n"
            "Где P — сумма кредита, r — месячная ставка, n — число месяцев.\n\n"
            "Дифференцированный платёж устроен иначе: основной долг делится на равные части, "
            "а проценты каждый месяц считаются на текущий остаток.\n\n"
            "Первый платёж на ваших данных\n"
            f"Остаток долга: {format_money(first.balance_before)}\n"
            f"Месячная ставка: {format_percent(first.monthly_rate)}\n"
            f"Начисленные проценты: {format_money(first.interest)}\n"
            f"Платёж: {format_money(first.regular_payment)}\n"
            f"Из него в основной долг пошло: {format_money(first.principal_paid)}\n"
            f"Досрочное погашение в этот период: {format_money(first.extra_payment)}\n"
            f"Новый остаток: {format_money(first.balance_after)}\n\n"
            "Подсказки по терминам\n"
            "Номинальная ставка — базовый процент банка без учёта всех дополнительных расходов.\n"
            "ГЭСВ — попытка показать реальную стоимость займа целиком.\n"
            "Основной долг — это тело кредита, которое вы возвращаете банку.\n"
            "Проценты — плата банку за использование денег.\n"
            "Досрочное погашение — дополнительная сумма сверх графика, которая снижает долг раньше срока.\n\n"
            "Важно\n"
            "Расчёт ориентировочный. Реальный график банка может отличаться из-за округлений, "
            "метода подсчёта дней, комиссий, страховок и правил конкретного договора."
        )

    def _set_explanation(self, text: str) -> None:
        self.explanation_box.configure(state="normal")
        self.explanation_box.delete("1.0", "end")
        self.explanation_box.insert("1.0", text or "После расчёта здесь появится понятное объяснение логики.")
        self.explanation_box.configure(state="disabled")

    def _set_results_placeholder(self) -> None:
        for label in self.metric_labels.values():
            label.configure(text="—")

    def _clear_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _export_csv(self) -> None:
        if self.result is None:
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить график",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="qaryzcalc_schedule.csv",
        )
        if not path:
            return

        export_schedule_to_csv(path, self.result)
        messagebox.showinfo("Экспорт завершён", "CSV-файл успешно сохранён.", parent=self)

    @staticmethod
    def _parse_date(raw: str, field_name: str) -> date:
        try:
            return datetime.strptime(raw.strip(), "%d.%m.%Y").date()
        except ValueError as exc:
            raise ValueError(f'Поле "{field_name}" должно быть в формате ДД.ММ.ГГГГ.') from exc

    @staticmethod
    def _parse_int(raw: str, field_name: str) -> int:
        cleaned = raw.strip()
        if not cleaned:
            raise ValueError(f'Поле "{field_name}" обязательно для заполнения.')
        try:
            return int(cleaned)
        except ValueError as exc:
            raise ValueError(f'Поле "{field_name}" должно быть целым числом.') from exc

    @staticmethod
    def _parse_required_decimal(raw: str, field_name: str) -> Decimal:
        if not raw.strip():
            raise ValueError(f'Поле "{field_name}" обязательно для заполнения.')
        return parse_decimal(raw, field_name)

    @staticmethod
    def _table_money(value: Decimal) -> str:
        return format_money(value).replace(" ₸", "")

    @staticmethod
    def _amount_to_input(value: Decimal) -> str:
        if value == value.quantize(Decimal("1")):
            return f"{int(value):,}".replace(",", " ")
        return f"{value:.2f}".replace(".", ",")

    @staticmethod
    def _decimal_to_input(value: Decimal) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")

    @staticmethod
    def _try_parse_decimal(raw: str) -> Decimal | None:
        if not raw.strip():
            return None
        try:
            return parse_decimal(raw, "Поле")
        except ValueError:
            return None

    def _current_mode(self) -> str:
        return "mortgage" if self.mode_var.get() == "Ипотека" else "loan"

    def _current_payment_type(self) -> str:
        return "annuity" if self.payment_type_var.get() == "Аннуитетный" else "differentiated"

    def _current_term_unit(self) -> str:
        return "years" if self.term_unit_var.get() == "Годы" else "months"
