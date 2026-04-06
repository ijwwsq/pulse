-- Представим архитектуру в виде 4 доменов. Люди, Продукты, Расписание, Финансы
--1 Категория Люди
--Общий справочник по всем людям в системе
CREATE TABLE persons (
    person_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    phone         VARCHAR(20)  NOT NULL UNIQUE,
    email         VARCHAR(100) UNIQUE,
    birth_date    DATE CHECK (birth_date < CURRENT_DATE),
    person_type   VARCHAR(20)  NOT NULL CHECK (person_type IN ('client', 'staff')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);
--Профиль клиентов
CREATE TABLE client_profiles (
    person_id         UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,
    registration_date DATE         NOT NULL DEFAULT CURRENT_DATE
);
-- Профиль сотрудника
CREATE TABLE staff_profiles (
    person_id         UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE RESTRICT,
    role              VARCHAR(30) NOT NULL CHECK (role IN ('trainer', 'admin', 'manager')),
    hire_date         DATE        NOT NULL DEFAULT CURRENT_DATE,
    -- NULL если сотрудник не тренер
    qualification_lvl VARCHAR(20) CHECK (qualification_lvl IN ('Level_1', 'Level_2', 'Elite')),
    rate_per_session  DECIMAL(10,2) CHECK (rate_per_session >= 0)
);

--Справочник специализаций, чтобы не было проблем если появится тренера по новому направлению 
CREATE TABLE specializations (
    specialization_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(50) NOT NULL UNIQUE -- 'Workout','Yoga'
);

--Связь М:М (у 1 тренера несколько специализаций и наоборот)
CREATE TABLE staff_specializations (
    staff_id          UUID REFERENCES persons(person_id) ON DELETE CASCADE,
    specialization_id UUID REFERENCES specializations(specialization_id) ON DELETE RESTRICT,
    PRIMARY KEY (staff_id, specialization_id)
);

--2 Категория продукты и всё что с ними связано
--Категории абонементов
CREATE TABLE membership_types (
    membership_type_id UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name               VARCHAR(50)   NOT NULL UNIQUE,
    description        TEXT,
    price              DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    duration_days      INTEGER       NOT NULL CHECK (duration_days > 0),
    -- NULL - безлимитный абонемент
    max_visits         INTEGER       CHECK (max_visits > 0),
    max_freezes        INTEGER       NOT NULL DEFAULT 0,
    guest_visits       INTEGER       NOT NULL DEFAULT 0
);
--Абонементы клиентов
CREATE TABLE subscriptions (
    subscription_id    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id          UUID    NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    membership_type_id UUID    NOT NULL REFERENCES membership_types(membership_type_id),
    start_date         DATE    NOT NULL DEFAULT CURRENT_DATE,
    end_date           DATE    NOT NULL,
    is_paid            BOOLEAN NOT NULL DEFAULT FALSE,
    sold_by_staff_id   UUID    REFERENCES persons(person_id), -- кто продал
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT date_order CHECK (end_date > start_date)
);
--Заморозки по абонементам(Можно анализировать историю + выставлять автоматом базовые случаи по типу бесплатных дней заморозок а не флагом да или нет)
CREATE TABLE subscription_freezes (
    freeze_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    freeze_start    DATE NOT NULL,
    freeze_end      DATE,
    reason          TEXT,
    CONSTRAINT freeze_dates CHECK (freeze_end IS NULL OR freeze_end > freeze_start)
);
--3 Расписание и всё что касается учёта посещения
--Информация по состоянию конкретного занятия
CREATE TABLE workout_types (
    workout_type_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(100) NOT NULL,
    category        VARCHAR(30)  NOT NULL CHECK (category IN ('HIIT', 'Strength', 'Recovery', 'Yoga')),
    intensity_level VARCHAR(20)  CHECK (intensity_level IN ('Low', 'Medium', 'High')),
    description     TEXT,
    max_capacity    INTEGER      NOT NULL DEFAULT 15 CHECK (max_capacity > 0)
);
--Тут уже четка информация с историчностью по конкретным занятиям
CREATE TABLE schedule (
    schedule_id     UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_type_id UUID    NOT NULL REFERENCES workout_types(workout_type_id),
    trainer_id      UUID    NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT,
    room_name       VARCHAR(50)  NOT NULL,
    start_time      TIMESTAMPTZ  NOT NULL,
    end_time        TIMESTAMPTZ  NOT NULL,
    is_cancelled    BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT time_order CHECK (end_time > start_time)
);
--Таблица событий. Тут статусы по посещениям, санкции для тех у кого условно не безлимит или с тренером. И историчность 
CREATE TABLE attendance (
    attendance_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID        NOT NULL REFERENCES persons(person_id),
    schedule_id     UUID        NOT NULL REFERENCES schedule(schedule_id),
    subscription_id UUID        REFERENCES subscriptions(subscription_id),
    booking_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_in_time   TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'booked'
                    CHECK (status IN ('booked', 'attended', 'cancelled', 'no-show')),
    -- Уникальность: один клиент — одна запись на одно занятие
    UNIQUE (client_id, schedule_id)
);
--4 Финансы
--Единый журнал по финансовым операциям по типу поля. Так как не так много всего удобно делать аналитику и работать, чтобы не запутаться
-- Для демо идеальное решение
CREATE TABLE transactions (
    transaction_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID          NOT NULL REFERENCES persons(person_id),
    staff_id        UUID          REFERENCES persons(person_id), -- кто провёл
    service_type    VARCHAR(30)   NOT NULL
                    CHECK (service_type IN ('subscription', 'personal_training', 'bar', 'test', 'penalty')),
    reference_id    UUID,         -- ID абонемента, занятия или другого объекта
    amount          DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    payment_status  VARCHAR(20)   NOT NULL DEFAULT 'pending'
                    CHECK (payment_status IN ('pending', 'paid', 'refunded', 'deposit')),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    notes           TEXT
);
--Штрафы. Тут и просрочки по занятиям или же сгорание абонемента без заморозки, в общем случаи разные и логика отдельная соответственно
CREATE TABLE penalties (
    penalty_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    attendance_id   UUID          NOT NULL REFERENCES attendance(attendance_id),
    transaction_id  UUID          REFERENCES transactions(transaction_id),
    amount          DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    reason          TEXT          NOT NULL,
    applied_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);