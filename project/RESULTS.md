# RESULTS.md — NL2SQL System Test Results

## Summary

| Metric | Value |
|---|---|
| Total questions tested | 20 |
| Passed | 20 |
| Failed | 0 |
| Pass rate | 100% |
| Avg execution time | 15096ms |
| LLM | Groq llama-3.3-70b-versatile |

---

### Q1 [OK] — How many patients do we have?

**Generated SQL:**
```sql
SELECT COUNT(id) FROM patients
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 11222ms
- **Summary:** The COUNT(id) is **200**.

---

### Q2 [OK] — List all female patients from Delhi

**Generated SQL:**
```sql
SELECT * FROM patients WHERE city = 'Delhi' AND gender = 'Female'
```
- **Status:** PASS
- **Rows returned:** 15
- **Chart type:** scatter
- **Execution time:** 4969ms
- **Summary:** Found **15** results.

---

### Q3 [OK] — Who is the busiest doctor?

**Generated SQL:**
```sql
SELECT d.name, COUNT(a.id) as total_appointments 
FROM doctors d 
JOIN appointments a ON d.id = a.doctor_id 
GROUP BY d.name 
ORDER BY total_appointments DESC 
LIMIT 1
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** bar
- **Execution time:** 4729ms
- **Summary:** Result — name: Dr. Priya Mehta | total_appointments: 52

---

### Q4 [OK] — How many doctors are in each specialization?

**Generated SQL:**
```sql
SELECT specialization, COUNT(id) FROM doctors GROUP BY specialization
```
- **Status:** PASS
- **Rows returned:** 5
- **Chart type:** bar
- **Execution time:** 3342ms
- **Summary:** Found **5** results.

---

### Q5 [OK] — Show all appointments in the last 30 days

**Generated SQL:**
```sql
SELECT * FROM appointments WHERE appointment_date >= DATE('now', '-30 days')
```
- **Status:** PASS
- **Rows returned:** 38
- **Chart type:** scatter
- **Execution time:** 3239ms
- **Summary:** Found **38** results.

---

### Q6 [OK] — How many appointments were cancelled?

**Generated SQL:**
```sql
SELECT COUNT(id) FROM appointments WHERE status = 'cancelled'
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 3788ms
- **Summary:** The COUNT(id) is **0**.

---

### Q7 [OK] — What is the total revenue from paid invoices?

**Generated SQL:**
```sql
SELECT SUM(total_amount) FROM invoices WHERE status = 'paid'
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 3109ms
- **Summary:** The SUM(total amount) is **None**.

---

### Q8 [OK] — List all overdue invoices with patient names

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, i.total_amount, i.due_date 
FROM invoices i 
JOIN patients p ON i.patient_id = p.id 
WHERE i.status = 'unpaid' AND i.due_date < CURRENT_DATE
```
- **Status:** PASS
- **Rows returned:** 0
- **Chart type:** -
- **Execution time:** 8089ms
- **Summary:** No data found for that query. Try adjusting your filters.

---

### Q9 [OK] — Show monthly appointment trends for this year

**Generated SQL:**
```sql
SELECT 
    STRFTIME('%Y-%m', appointment_date) AS month,
    COUNT(id) AS total_appointments
FROM 
    appointments
WHERE 
    STRFTIME('%Y', appointment_date) = STRFTIME('%Y', 'now')
GROUP BY 
    STRFTIME('%Y-%m', appointment_date)
ORDER BY 
    month ASC
```
- **Status:** PASS
- **Rows returned:** 4
- **Chart type:** scatter
- **Execution time:** 51873ms
- **Summary:** Found **4** results.

---

### Q10 [OK] — Which city has the most patients?

**Generated SQL:**
```sql
SELECT city FROM patients GROUP BY city ORDER BY COUNT(id) DESC LIMIT 1
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 7751ms
- **Summary:** The city is **Mumbai**.

---

### Q11 [OK] — Top 5 patients by total spending

**Generated SQL:**
```sql
SELECT p.first_name, p.last_name, SUM(i.total_amount) as total_spending 
FROM patients p 
JOIN invoices i ON p.id = i.patient_id 
GROUP BY p.id 
ORDER BY total_spending DESC 
LIMIT 5
```
- **Status:** PASS
- **Rows returned:** 5
- **Chart type:** bar
- **Execution time:** 40610ms
- **Summary:** Found **5** results.

---

### Q12 [OK] — What is the average cost of treatments?

**Generated SQL:**
```sql
SELECT AVG(cost) FROM treatments
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 9348ms
- **Summary:** The AVG(cost) is **2460.328631921824**.

---

### Q13 [OK] — Show revenue by doctor

**Generated SQL:**
```sql
SELECT d.name, SUM(i.total_amount) as revenue 
FROM invoices i 
JOIN appointments a ON i.appointment_id = a.id 
JOIN doctors d ON a.doctor_id = d.id 
GROUP BY d.name
```
- **Status:** PASS
- **Rows returned:** 15
- **Chart type:** bar
- **Execution time:** 41866ms
- **Summary:** Found **15** results.

---

### Q14 [OK] — How many patients does each doctor treat?

**Generated SQL:**
```sql
SELECT doctor_id, COUNT(patient_id) FROM appointments GROUP BY doctor_id
```
- **Status:** PASS
- **Rows returned:** 15
- **Chart type:** -
- **Execution time:** 20706ms
- **Summary:** Found **15** results.

---

### Q15 [OK] — List treatments done by Cardiology doctors

**Generated SQL:**
```sql
SELECT t.treatment_name 
FROM treatments t 
JOIN appointments a ON t.appointment_id = a.id 
JOIN doctors d ON a.doctor_id = d.id 
WHERE d.specialization = 'Cardiology'
```
- **Status:** PASS
- **Rows returned:** 59
- **Chart type:** -
- **Execution time:** 12792ms
- **Summary:** Found **59** results.

---

### Q16 [OK] — How many appointments happened in the last 3 months?

**Generated SQL:**
```sql
SELECT COUNT(*) FROM appointments WHERE appointment_date >= DATE('now', '-3 month')
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 26169ms
- **Summary:** The COUNT(*) is **123**.

---

### Q17 [OK] — What percentage of invoices are paid?

**Generated SQL:**
```sql
SELECT CAST(SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM invoices
```
- **Status:** PASS
- **Rows returned:** 1
- **Chart type:** -
- **Execution time:** 7113ms
- **Summary:** The CAST(SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) is **0.0**.

---

### Q18 [OK] — Show the most common treatments

**Generated SQL:**
```sql
SELECT treatment_name, COUNT(*) as frequency 
FROM treatments 
GROUP BY treatment_name 
ORDER BY frequency DESC;
```
- **Status:** PASS
- **Rows returned:** 25
- **Chart type:** bar
- **Execution time:** 24301ms
- **Summary:** Found **25** results.

---

### Q19 [OK] — Which month had the highest revenue?

**Generated SQL:**
```sql
SELECT STRFTIME('%m', invoice_date) AS month, SUM(total_amount) AS revenue 
FROM invoices 
WHERE status = 'paid' 
GROUP BY STRFTIME('%m', invoice_date) 
ORDER BY revenue DESC 
LIMIT 1
```
- **Status:** PASS
- **Rows returned:** 0
- **Chart type:** -
- **Execution time:** 9647ms
- **Summary:** No data found for that query. Try adjusting your filters.

---

### Q20 [OK] — List patients who have had more than 3 appointments

**Generated SQL:**
```sql
SELECT p.id, p.first_name, p.last_name, COUNT(a.id) as appointment_count 
FROM patients p 
JOIN appointments a ON p.id = a.patient_id 
GROUP BY p.id, p.first_name, p.last_name 
HAVING COUNT(a.id) > 3
```
- **Status:** PASS
- **Rows returned:** 39
- **Chart type:** bar
- **Execution time:** 7271ms
- **Summary:** Found **39** results.

---

## Failure Analysis

All questions passed successfully.