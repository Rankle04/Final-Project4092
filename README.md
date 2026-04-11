# CS4092 Online Shopping - Backend

## Quick Start

### 1. Setup PostgreSQL
```bash
createdb shopping
psql -d shopping -f database/schema.sql
```

### 2. Run Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Server runs at `http://localhost:5000`.

### Environment Variables (optional)
```
DB_HOST=localhost  DB_PORT=5432  DB_NAME=shopping
DB_USER=postgres   DB_PASS=postgres  SECRET_KEY=your-secret
```

## API Reference

### Auth
| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/register` | `{email, password, first_name, last_name}` | Register customer |
| POST | `/api/login` | `{email, password}` | Login (customer or staff) |
| POST | `/api/logout` | - | Logout |
| GET | `/api/me` | - | Current user info |

### Products (public browse, staff CRUD)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products?search=&category=&type=` | Browse/search products |
| GET | `/api/products/:id` | Product detail |
| POST | `/api/products` | Create product (staff) |
| PUT | `/api/products/:id` | Update product (staff) |
| DELETE | `/api/products/:id` | Delete product (staff) |
| GET | `/api/categories` | List categories |

### Cart (customer)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cart` | View cart |
| POST | `/api/cart` | Add item `{product_id, quantity}` |
| PUT | `/api/cart/:item_id` | Update quantity `{quantity}` |
| DELETE | `/api/cart/:item_id` | Remove item |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orders` | Place order `{card_id, delivery_type}` |
| GET | `/api/orders` | List orders |
| GET | `/api/orders/:id` | Order detail |
| PUT | `/api/orders/:id/status` | Update status (staff) `{status}` |

### Addresses & Cards (customer)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/addresses` | List / Add address |
| PUT/DELETE | `/api/addresses/:id` | Update / Delete address |
| GET/POST | `/api/cards` | List / Add credit card |
| PUT/DELETE | `/api/cards/:id` | Update / Delete card |

### Stock & Warehouse (staff)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/warehouses` | List warehouses |
| POST | `/api/stock` | Add stock `{product_id, warehouse_id, quantity}` |
| GET | `/api/customers` | List customers (staff) |

## Default Staff Login
- Email: `admin@shop.com` / Password: `admin123`

## Bonus Features Implemented
- ✅ Check availability when placing orders
- ✅ Warehouse capacity check when adding stock
- ✅ Product images (image_url field)
- ✅ Supplier tables in schema
