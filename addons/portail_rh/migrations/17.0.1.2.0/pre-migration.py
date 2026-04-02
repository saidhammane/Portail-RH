def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_travel_request AS tr
           SET employee_id = emp.id
          FROM hr_employee AS emp
         WHERE tr.employee_id IS NULL
           AND emp.user_id = tr.create_uid
        """
    )

    cr.execute(
        """
        UPDATE hr_travel_request
           SET date_from = COALESCE(date_from, create_date::date, CURRENT_DATE),
               date_to = COALESCE(date_to, date_from, create_date::date, CURRENT_DATE)
         WHERE date_from IS NULL
            OR date_to IS NULL
        """
    )

    cr.execute(
        """
        UPDATE hr_travel_request
           SET state = 'draft'
         WHERE state IS NULL
        """
    )
