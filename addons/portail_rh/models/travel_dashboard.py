from odoo import fields, models, tools


class HrTravelRequestReport(models.Model):
    _name = "hr.travel.request.report"
    _description = "Tableau de bord des demandes de deplacement"
    _auto = False
    _rec_name = "month"

    month = fields.Char(string="Mois", readonly=True)
    month_start = fields.Date(string="Mois (debut)", readonly=True)
    state = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("submitted", "Soumis"),
            ("approved", "Approuve"),
            ("rejected", "Refuse"),
            ("done", "Termine"),
        ],
        string="Etat",
        readonly=True,
    )
    request_count = fields.Integer(string="Nombre de demandes", readonly=True)
    total_estimated_cost = fields.Float(string="Cout estime total", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            """
            CREATE OR REPLACE VIEW hr_travel_request_report AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY src.report_month, src.state) AS id,
                    TO_CHAR(src.report_month::date, 'YYYY-MM') AS month,
                    src.report_month::date AS month_start,
                    src.state AS state,
                    COUNT(*)::integer AS request_count,
                    COALESCE(SUM(src.estimated_cost), 0.0) AS total_estimated_cost
                FROM (
                    SELECT
                        date_trunc(
                            'month',
                            COALESCE(r.date_from::timestamp, r.create_date)
                        ) AS report_month,
                        r.state AS state,
                        COALESCE(r.estimated_cost, 0.0) AS estimated_cost
                    FROM hr_travel_request r
                ) src
                GROUP BY src.report_month, src.state
            )
            """
        )
