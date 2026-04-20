--По номеру телефона(полезно)
CREATE INDEX idx_persons_phone ON persons(phone);

-- Поиск активных абонементов для конкретного клиента
CREATE INDEX idx_subscriptions_client_date 
    ON subscriptions(client_id, end_date) 
    WHERE is_paid = TRUE;

--Индекс Посещаемости по занятию
CREATE INDEX idx_attendance_schedule ON attendance(schedule_id);

--Посещаемость по клиенту(полезно если будет много записей)
CREATE INDEX idx_attendance_client ON attendance(client_id);

--Транзакции по клиенту и дате
CREATE INDEX idx_transactions_client_date ON transactions(client_id, created_at DESC);