**Проект 8: «Управление фитнес-пространством "Pulse"»**

**«Pulse»** — это сеть концептуальных фитнес-студий, ориентированная на функциональный тренинг, биохакинг и персональное сопровождение клиентов. Студия известна своим технологичным подходом к тренировкам и гибкой системой членства.

**Нынешняя система**

В студии **«Pulse»** в настоящее время проводится реорганизация системы контроля доступа и учета услуг. Ранее данные о клиентах и их активности фиксировались в разрозненных таблицах и CRM-черновиках.

Сведения о резидентах хранятся в файле **«База атлетов»**. Этот файл содержит ID клиента, ФИО, номер телефона, статус биометрического профиля и дату последней активности. Детализация доступных продуктов находится в файле **«Тарифная сетка»**, который включает типы подписок (Full Pass, Morning, PT Only), их стоимость, лимиты по гостевым визитам и количество заморозок.

Для координации работы залов используется файл **«Сетка занятий»**, где указаны коды тренировок, категории (HIIT, Strength, Recovery), время начала, ID тренера и максимальный лимит участников. Информация о команде — ID сотрудника, квалификация (Level 1, 2, Elite), специализация и контактные данные — находится в файле **«Team»**.

При записи на персональное сопровождение или покупке доп. услуг (фитнес-бар, тесты на газоанализаторе) заполняется **Форма транзакции**:

**ФОРМА ТРАНЗАКЦИИ**

- **ID операции:**
- **ID клиента:**
- **Тип услуги (Подписка / Доп. услуга):**
- **ID сотрудника (продавец/тренер):**
- **Дата и время:**
- **Сумма:**
- **Статус оплаты (Оплачено / Депозит):**

**Разработанная система**

Руководство **«Pulse»** приняло решение полностью автоматизировать операционные процессы, чтобы исключить человеческий фактор при проверке допусков в зоны тренировок и минимизировать ошибки в расчетах с тренерами. Разработка поручена внутреннему IT-департаменту компании.

**В рамках новой системы реализованы следующие модули:**

1. **Модуль управления доступом и подписками:** Позволяет мгновенно проверять статус членства на турникетах. Система автоматически списывает посещения из пакета услуг и уведомляет клиента о необходимости продления подписки за 3 дня до окончания срока.
2. **Smart-расписание и бронирование:** Система позволяет клиентам резервировать место в группе или слот у персонального тренера. Учитывается ограничение по вместимости залов (не более 15 человек на функциональную зону). При отмене брони менее чем за 2 часа система автоматически применяет штраф согласно правилам студии.
3. **Система Performance-учета тренеров:** На основе фактически проведенных сессий и отзывов клиентов система рассчитывает переменную часть вознаграждения для каждого сотрудника, учитывая коэффициент его категории и количество персональных тренировок.
4. **Аналитический дашборд:** Позволяет менеджменту отслеживать LTV (пожизненную ценность клиента), процент продлений абонементов и пиковые часы нагрузки для эффективного управления штатом клининга и дежурных администраторов.

🐘 **План реализации проекта «Pulse» (PostgreSQL)**

**Неделя 9: Инициализация и DDL**

- **Задачи:** Исследование процессов студии. Развертывание БД. Создание схемы данных.
- **Реализация:** * Создание таблиц: clients, membership_types, subscriptions, trainers, workout_types, schedule.
    - Использование специфичных для Postgres типов: UUID для первичных ключей, TIMESTAMPTZ для времени с учетом часового пояса.
    - Заполнение тестовыми данными (30+ строк) через INSERT INTO ... VALUES.
- **Результат:** Чистый SQL-скрипт инициализации.

**Неделя 10: Группировка и Целостность**

- **Задачи:** Сложная аналитика и настройка связей.
- **Реализация:**
    - Написание 5 запросов с GROUP BY и HAVING (например: «Найти тренеров, у которых средняя оценка выше 4.8»).
    - Использование подзапросов в WHERE и FROM.
    - Настройка ограничений: PRIMARY KEY, FOREIGN KEY с правилами ON DELETE RESTRICT.
- **Результат:** Отчет по аналитике и описание связей.

**Неделя 11: Joins, ER-моделирование и Нормализация**

- **Задачи:** Связывание данных и иерархии.
- **Реализация:**
    - Сложные JOIN (включая LATERAL JOIN, если потребуется для расписания).
    - Реализация иерархии через **Наследование таблиц** (Table Inheritance) или общую таблицу с типом (Discriminated Union) для сотрудников и клиентов.
    - Приведение к **3NF**: вынос специализаций в отдельную таблицу-справочник.
- **Результат:** ER-диаграмма в UML/Mermaid и скрипт обновления структуры.

**Неделя 12: Процедурный код (PL/pgSQL)**

- **Задачи:** Автоматизация логики на стороне сервера.
- **Реализация:**
    - **Views:** Создание v_active_subscriptions для быстрого доступа к текущим клиентам.
    - **Functions/Stored Procedures:** Написание функций на языке plpgsql (например, функция check_in_client(client_id)).
    - **Triggers:** Создание триггера tg_update_last_visit, который срабатывает после входа клиента.
- **Результат:** Код функций и триггеров с комментариями.

**Неделя 13: Безопасность и Транзакции**

- **Задачи:** Управление доступом и отказоустойчивость.
- **Реализация:**
    - **DCL:** Создание ролей (coach, receptionist, admin) и выдача прав через GRANT.
    - **Transactions:** Отработка сценария покупки абонемента с использованием BEGIN, COMMIT, ROLLBACK и обработкой исключений (EXCEPTION).
    - **Locks:** Тестирование блокировок строк (SELECT FOR UPDATE) для предотвращения двойной записи на одно место.
- **Результат:** Скрипт настройки безопасности.

**Неделя 14: Индексы и Оптимизация**

- **Задачи:** Ускорение и защита.
- **Реализация:**
    - Создание B-tree индексов для поиска по телефону и GIN индексов (если будет полнотекстовый поиск по описанию тренировок).
    - **EXPLAIN ANALYZE:** Оптимизация 5 медленных запросов.
    - **Encryption:** Использование расширения pgcrypto для шифрования чувствительных данных.
- **Результат:** Финальная презентация и полный SQL-дамп проекта.

## Примерная реализация таблиц

```sql
-- Включаем расширение для генерации UUID (универсальных идентификаторов)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Справочник типов членства (Тарифы)
CREATE TABLE membership_types (
    membership_type_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE, -- Названия: 'Full Pass', 'Morning', 'Pro'
    description TEXT,
    price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    max_visits INTEGER -- NULL если безлимит
);

-- 2. Основная таблица клиентов (Резиденты)
CREATE TABLE clients (
    client_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    birth_date DATE CHECK (birth_date < CURRENT_DATE),
    registration_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. Сотрудники (Тренеры и Администраторы)
CREATE TABLE staff (
    staff_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    role VARCHAR(30) NOT NULL CHECK (role IN ('trainer', 'admin', 'manager')),
    specialization VARCHAR(100), -- Например: 'Yoga', 'HIIT', 'Powerlifting'
    hire_date DATE DEFAULT CURRENT_DATE,
    phone VARCHAR(20) NOT NULL UNIQUE
);

-- 4. Абонементы клиентов (Связь клиента и тарифа)
CREATE TABLE subscriptions (
    subscription_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id uuid REFERENCES clients(client_id) ON DELETE CASCADE,
    membership_type_id uuid REFERENCES membership_types(membership_type_id),
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date DATE NOT NULL,
    visits_left INTEGER, -- Сколько осталось из max_visits
    is_paid BOOLEAN DEFAULT FALSE,
    CONSTRAINT date_check CHECK (end_date >= start_date)
);

-- 5. Типы тренировок
CREATE TABLE workout_types (
    workout_type_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(100) NOT NULL,
    intensity_level VARCHAR(20) CHECK (intensity_level IN ('Low', 'Medium', 'High')),
    max_capacity INTEGER DEFAULT 15
);

-- 6. Расписание занятий
CREATE TABLE schedule (
    schedule_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workout_type_id uuid REFERENCES workout_types(workout_type_id),
    trainer_id uuid REFERENCES staff(staff_id),
    room_name VARCHAR(50) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    CONSTRAINT duration_check CHECK (end_time > start_time)
);

-- 7. Журнал посещений и записей
CREATE TABLE attendance (
    attendance_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id uuid REFERENCES clients(client_id),
    schedule_id uuid REFERENCES schedule(schedule_id),
    check_in_time TIMESTAMPTZ, -- Время фактического прихода
    status VARCHAR(20) DEFAULT 'booked' CHECK (status IN ('booked', 'attended', 'cancelled', 'no-show'))
);
```

### 1. Стек технологий (Technology Stack)

Выбранный стек ориентирован на высокую производительность, строгую типизацию данных и скорость разработки прототипа.

| Уровень | Технология | Роль в проекте |
| --- | --- | --- |
| **Database** | **PostgreSQL 16+** | Хранение данных, обеспечение целостности (FK, Constraints), процедурная логика (PL/pgSQL). |
| **Backend** | **Python 3.11+ / FastAPI** | Создание асинхронного API, обработка бизнес-логики, маршрутизация запросов. |
| **Database Driver** | **psycopg[binary]** | Высокопроизводительное прямое подключение к PostgreSQL для выполнения SQL-запросов. |
| **Templating** | **Jinja2** | Серверный рендеринг динамических HTML-страниц (Server-Side Rendering). |
| **Frontend UI** | **Tailwind CSS + DaisyUI** | Современный интерфейс через готовые компоненты (карточки, таблицы, модальные окна). |

### 2. Схема взаимодействия элементов (System Architecture)

Система строится по классической монолитной архитектуре с четким разделением слоев доступа.

1. **Клиентский уровень (Frontend):** Пользователь открывает браузер. Интерфейс на DaisyUI отправляет HTTP-запросы (GET/POST) на сервер.
2. **Уровень приложения (Backend):** FastAPI принимает запрос.
    - Если это запрос страницы (`/`), он запрашивает данные из БД и через Jinja2 собирает HTML.
    - Если это действие (например, «Записать на тренировку»), он вызывает соответствующую функцию или **Хранимую процедуру** в БД.
3. **Уровень данных (Database):** PostgreSQL выполняет запрос. При этом срабатывают **триггеры** (например, списание занятия с абонемента) и проверяются **ограничения** (Constraints), гарантируя, что в зале не окажется 16 человек при лимите 15.

### 3. Схема потоков данных (Data Flow)

Ниже описана логика прохождения данных на примере процесса **«Регистрация визита клиента»**:

1. **Action:** Администратор вводит номер телефона клиента в UI.
2. **Request:** Браузер отправляет `POST /check-in` с ID клиента.
3. **Validation:** FastAPI проверяет наличие активной сессии.
4. **Database Execution:** * Вызов процедуры `CALL sp_register_visit(client_id)`.
    - БД проверяет: `subscriptions.end_date >= CURRENT_DATE` и `visits_left > 0`.
    - Если условия верны — `visits_left` уменьшается на 1, создается запись в `attendance`.
5. **Response:** Сервер возвращает статус `200 OK`, и UI обновляет статистику «Человек в зале».

### 4. Инфраструктурные требования

- **СУБД:** Должна поддерживать расширение `uuid-ossp` для генерации идентификаторов.
- **Безопасность:** Доступ к БД ограничен ролями (DCL). Пароли сотрудников и конфиденциальные данные клиентов должны обрабатываться с использованием методов шифрования (на этапе Недели 14).
- **Среда исполнения:** Python-приложение запускается через асинхронный сервер **Uvicorn**.

---

## Запуск Web API и UI

1. Поднимите PostgreSQL c автосозданием схемы, процедур, view и тестовых данных:

```bash
docker compose up -d postgres
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Укажите строку подключения в переменной окружения `DATABASE_URL`.

Пример:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/pulse"
```

4. Запустите приложение:

```bash
uvicorn app.main:app --reload
```

5. Откройте интерфейсы:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/client
http://127.0.0.1:8000/trainer
http://127.0.0.1:8000/admin
```

## Реализованные endpoints

- `GET /health`
- `GET /api/dashboard`
- `GET /api/clients?search=`
- `GET /api/trainers`
- `GET /api/membership-types`
- `GET /api/schedule?date_from=&date_to=`
- `GET /api/subscriptions/active`
- `POST /api/bookings`
- `POST /api/check-in`
- `POST /api/subscriptions`
- `POST /api/transactions`
- `GET /api/analytics/{view_name}?limit=`
- `GET /api/lookups`
- `GET /api/client/{client_id}/overview`
- `GET /api/trainer/{trainer_id}/overview`
- `GET /api/admin/metrics`

Доступные аналитические view:

- `v_sales_analytics`
- `v_client_activity`
- `v_trainer_performance`
- `v_workout_popularity`
- `v_financial_summary`
- `v_active_subscriptions`