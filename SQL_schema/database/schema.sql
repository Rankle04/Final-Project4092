-- ============================================================
-- CS4092 Online Shopping Application - Database Schema
-- PostgreSQL
-- ============================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS order_item CASCADE;
DROP TABLE IF EXISTS delivery_plan CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS cart_item CASCADE;
DROP TABLE IF EXISTS stock CASCADE;
DROP TABLE IF EXISTS supplier_product CASCADE;
DROP TABLE IF EXISTS supplier CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS category CASCADE;
DROP TABLE IF EXISTS warehouse CASCADE;
DROP TABLE IF EXISTS credit_card CASCADE;
DROP TABLE IF EXISTS customer_address CASCADE;
DROP TABLE IF EXISTS staff CASCADE;
DROP TABLE IF EXISTS customer CASCADE;
DROP TABLE IF EXISTS address CASCADE;

-- ============================================================
-- Address (shared by customers, staff, warehouses, suppliers)
-- ============================================================
CREATE TABLE address (
    address_id   SERIAL PRIMARY KEY,
    street       VARCHAR(255) NOT NULL,
    city         VARCHAR(100) NOT NULL,
    state        VARCHAR(100),
    zip_code     VARCHAR(20),
    country      VARCHAR(100) NOT NULL DEFAULT 'US'
);

-- ============================================================
-- Customer
-- ============================================================
CREATE TABLE customer (
    customer_id  SERIAL PRIMARY KEY,
    email        VARCHAR(255) UNIQUE NOT NULL,
    password     VARCHAR(255) NOT NULL,
    first_name   VARCHAR(100) NOT NULL,
    last_name    VARCHAR(100) NOT NULL,
    balance      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

-- A customer can have multiple addresses (delivery / payment)
CREATE TABLE customer_address (
    customer_id  INT NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    address_id   INT NOT NULL REFERENCES address(address_id) ON DELETE CASCADE,
    address_type VARCHAR(20) NOT NULL CHECK (address_type IN ('delivery', 'payment', 'both')),
    is_default   BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (customer_id, address_id)
);

-- Credit card (each linked to a payment address)
CREATE TABLE credit_card (
    card_id         SERIAL PRIMARY KEY,
    customer_id     INT NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    card_number     VARCHAR(20) NOT NULL,
    cardholder_name VARCHAR(200) NOT NULL,
    expiry_date     VARCHAR(7) NOT NULL,   -- MM/YYYY
    billing_address INT NOT NULL REFERENCES address(address_id),
    is_default      BOOLEAN NOT NULL DEFAULT FALSE
);

-- ============================================================
-- Staff
-- ============================================================
CREATE TABLE staff (
    staff_id    SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    address_id  INT REFERENCES address(address_id),
    salary      NUMERIC(10,2),
    job_title   VARCHAR(100)
);

-- ============================================================
-- Product catalog
-- ============================================================
CREATE TABLE category (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE product (
    product_id   SERIAL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    brand        VARCHAR(100),
    product_type VARCHAR(100),
    size         VARCHAR(50),
    description  TEXT,
    price        NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    category_id  INT REFERENCES category(category_id),
    image_url    TEXT,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Warehouse & Stock
-- ============================================================
CREATE TABLE warehouse (
    warehouse_id SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    address_id   INT NOT NULL REFERENCES address(address_id),
    capacity     INT  -- bonus: warehouse capacity
);

CREATE TABLE stock (
    stock_id     SERIAL PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES product(product_id) ON DELETE CASCADE,
    warehouse_id INT NOT NULL REFERENCES warehouse(warehouse_id) ON DELETE CASCADE,
    quantity     INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    UNIQUE (product_id, warehouse_id)
);

-- ============================================================
-- Shopping Cart
-- ============================================================
CREATE TABLE cart_item (
    cart_item_id SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customer(customer_id) ON DELETE CASCADE,
    product_id   INT NOT NULL REFERENCES product(product_id) ON DELETE CASCADE,
    quantity     INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    UNIQUE (customer_id, product_id)
);

-- ============================================================
-- Orders
-- ============================================================
CREATE TABLE orders (
    order_id     SERIAL PRIMARY KEY,
    customer_id  INT NOT NULL REFERENCES customer(customer_id),
    card_id      INT NOT NULL REFERENCES credit_card(card_id),
    status       VARCHAR(20) NOT NULL DEFAULT 'issued'
                 CHECK (status IN ('issued', 'sent', 'received')),
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE order_item (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id    INT NOT NULL REFERENCES product(product_id),
    quantity      INT NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL
);

CREATE TABLE delivery_plan (
    delivery_id   SERIAL PRIMARY KEY,
    order_id      INT UNIQUE NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    delivery_type VARCHAR(20) NOT NULL DEFAULT 'standard'
                  CHECK (delivery_type IN ('standard', 'express')),
    delivery_price NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    ship_date     DATE,
    delivery_date DATE
);

-- ============================================================
-- Bonus: Suppliers
-- ============================================================
CREATE TABLE supplier (
    supplier_id  SERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    address_id   INT REFERENCES address(address_id)
);

CREATE TABLE supplier_product (
    supplier_id  INT NOT NULL REFERENCES supplier(supplier_id) ON DELETE CASCADE,
    product_id   INT NOT NULL REFERENCES product(product_id) ON DELETE CASCADE,
    supply_price NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (supplier_id, product_id)
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_product_category ON product(category_id);
CREATE INDEX idx_product_name ON product(name);
CREATE INDEX idx_product_type ON product(product_type);
CREATE INDEX idx_stock_product ON stock(product_id);
CREATE INDEX idx_stock_warehouse ON stock(warehouse_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_item_order ON order_item(order_id);
CREATE INDEX idx_cart_customer ON cart_item(customer_id);
CREATE INDEX idx_credit_card_customer ON credit_card(customer_id);
CREATE INDEX idx_customer_email ON customer(email);

-- ============================================================
-- Seed data
-- ============================================================
INSERT INTO category (category_name) VALUES
  ('Apparel'), ('Food'), ('Electronics'), ('Books'), ('Home & Garden');

INSERT INTO address (street, city, state, zip_code, country) VALUES
  ('123 Main St', 'New York', 'NY', '10001', 'US'),
  ('456 Oak Ave', 'Los Angeles', 'CA', '90001', 'US'),
  ('789 Pine Rd', 'Chicago', 'IL', '60601', 'US');

INSERT INTO warehouse (name, address_id, capacity) VALUES
  ('East Warehouse', 1, 10000),
  ('West Warehouse', 2, 8000);

INSERT INTO staff (email, password, first_name, last_name, address_id, salary, job_title) VALUES
  ('admin@shop.com', 'admin123', 'Admin', 'User', 3, 60000, 'Manager');

INSERT INTO product (name, brand, product_type, size, description, price, category_id) VALUES
  ('Running Shoes', 'Nike', 'Shoes', '10', 'Comfortable running shoes', 99.99, 1),
  ('Red Apple', 'FreshFarm', 'Fruit', NULL, 'Fresh organic apple', 0.99, 2),
  ('Laptop', 'Dell', 'Computer', '15-inch', 'Powerful laptop for work', 899.99, 3),
  ('Python Cookbook', 'OReilly', 'Programming', NULL, 'Learn Python recipes', 39.99, 4),
  ('Desk Lamp', 'IKEA', 'Lighting', NULL, 'LED desk lamp', 24.99, 5);

INSERT INTO stock (product_id, warehouse_id, quantity) VALUES
  (1, 1, 100), (2, 1, 500), (3, 1, 50),
  (4, 2, 200), (5, 2, 150);
