# Instruções: CRUD Angular ↔ `GET/POST/PATCH/PUT/DELETE /api/people/`

Documento apenas orientativo para montar formulários e serviços HTTP no Angular, alinhado ao código atual em `core` (Django REST Framework).

---

## 1. URL base e `Content-Type`

| Item | Valor |
|------|--------|
| Prefixo global | `/api/` (ver `config/urls.py`) |
| Recurso | `/api/people/` |
| Lista | `GET /api/people/` · `POST /api/people/` |
| Detalhe | `GET /api/people/{id}/` · `PATCH` / `PUT` / `DELETE /api/people/{id}/` |
| Corpo | `Content-Type: application/json` |
| Resposta | JSON (objeto ou lista paginada) |

**Nota sobre `JSONField`:** o modelo **`Person` não tem `JSONField`**. Os dados são campos escalares + FK em JSON HTTP. Quem tem `JSONField` é **`Schedule.weekdays`** (`/api/schedules/`), não `/api/people/`.

**Sobre `Allow: GET, POST, HEAD, OPTIONS`:** isso costuma aparecer na **lista** (`/api/people/`). No **detalhe** (`/api/people/{id}/`), o DRF `ModelViewSet` também expõe normalmente `PUT`, `PATCH`, `DELETE`. Se no teu ambiente só aparecerem GET/POST, confirma no browser/Postman o `OPTIONS` em `.../people/1/`.

---

## 2. Autenticação (recomendado no Angular)

O projeto usa JWT (`Bearer` + access token do login). Mesmo que a permissão global não force `IsAuthenticated` em todos os viewsets, envia:

```http
Authorization: Bearer <access_token>
```

---

## 3. Paginação da lista (`GET /api/people/`)

`PageNumberPagination` com `PAGE_SIZE: 10`.

| Query | Exemplo |
|-------|---------|
| Página | `?page=2` |

Resposta típica:

```json
{
  "count": 42,
  "next": "http://host/api/people/?page=3",
  "previous": "http://host/api/people/?page=1",
  "results": [ { "...": "cada Person" } ]
}
```

No Angular, lê `results` para a tabela e `count`/`next`/`previous` para o paginador.

---

## 4. Filtros (`GET /api/people/?...`)

`PersonFilter` (`core/filters.py`):

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `company_id` | número | FK `company` |
| `type` | string | `DRIVER` ou `EMPLOYEE` |
| `is_active` | boolean | registo ativo |

Exemplo: `/api/people/?company_id=1&type=EMPLOYEE&is_active=true`

---

## 5. Formato JSON de uma `Person` (leitura)

Campos expostos pelo `PersonSerializer` (`fields = "__all__"` + `auto_email`):

| Campo | Tipo JSON | Leitura | Escrita (POST/PATCH) |
|-------|-----------|---------|------------------------|
| `id` | number | sim | **não** (read-only) |
| `company` | number | ID da empresa | enviar **ID** (inteiro) |
| `company_name` | string | nome da empresa | **não** (read-only) |
| `name` | string | sim | sim (max 255) |
| `phone` | string | sim | sim (max 30) |
| `type` | string | sim | sim: **`DRIVER`** ou **`EMPLOYEE`** |
| `license_number` | string \| null | sim | sim (obrigatório se `DRIVER`) |
| `employee_code` | string \| null | sim | sim (obrigatório se `EMPLOYEE`) |
| `is_active` | boolean | sim | sim (default `true`) |
| `created_at` | string (ISO 8601) | sim | **não** |
| `updated_at` | string (ISO 8601) | sim | **não** |
| `auto_email` | string \| null | sim | **não** (calculado: `employee_code` ou `license_number` + domínio da empresa) |

**FK `company`:** o JSON usa `company` como **ID numérico** para escrita/filtros e `company_name` para exibição na UI.

### Exemplo `GET` — resposta de um registo

```json
{
  "id": 5,
  "company": 1,
  "company_name": "SAMSUNG",
  "name": "Ana Costa",
  "phone": "+5511999990000",
  "type": "EMPLOYEE",
  "license_number": null,
  "employee_code": "EMP-1024",
  "is_active": true,
  "created_at": "2026-05-01T12:00:00Z",
  "updated_at": "2026-05-10T08:30:00Z",
  "auto_email": "emp-1024@empresa.com"
}
```

---

## 6. Regras de negócio para inputs (validação espelhada no front)

Alinhado a `Person.clean()` no modelo:

### Tipo `DRIVER`

- `license_number`: **obrigatório** (não vazio).
- `employee_code`: deve ficar **vazio / null** (se enviares string, o backend pode rejeitar).

### Tipo `EMPLOYEE`

- `employee_code`: **obrigatório** (não vazio).
- `license_number`: deve ficar **vazio / null**.

Erros de validação vêm como JSON do DRF, por campo, por exemplo:

```json
{
  "license_number": ["Driver precisa de license_number."]
}
```

ou

```json
{
  "employee_code": ["Employee precisa de employee_code."]
}
```

No Angular, mapeia `error.error` para mensagens por control (`FormGroup`).

---

## 7. Corpos mínimos para `POST`

**Funcionário (employee):**

```json
{
  "company": 1,
  "name": "Ana Costa",
  "phone": "+5511999990000",
  "type": "EMPLOYEE",
  "employee_code": "EMP-1024",
  "license_number": null,
  "is_active": true
}
```

**Motorista (driver):**

```json
{
  "company": 1,
  "name": "Bruno Silva",
  "phone": "+5511888880000",
  "type": "DRIVER",
  "license_number": "CNH123456",
  "employee_code": null,
  "is_active": true
}
```

---

## 8. `PATCH` vs `PUT`

- **`PATCH`:** envia só os campos alterados (recomendado em formulários de edição).
- **`PUT`:** substitui o recurso; em geral tens de enviar todos os campos obrigatórios coerentes com o `type`.

---

## 9. Interface TypeScript sugerida (Angular)

```typescript
export type PersonType = 'DRIVER' | 'EMPLOYEE';

export interface Person {
  id: number;
  company: number;
  company_name: string;
  name: string;
  phone: string;
  type: PersonType;
  license_number: string | null;
  employee_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  auto_email: string | null;
}

export interface PaginatedPeople {
  count: number;
  next: string | null;
  previous: string | null;
  results: Person[];
}
```

Para **criar**, podes usar `Omit<Person, 'id' | 'created_at' | 'updated_at' | 'auto_email'>` ou um DTO explícito com os campos que envias no `POST`.

---

## 10. Alternativa aos endpoints “genéricos”

O mesmo modelo `Person` é filtrado em:

- `/api/drivers/` — só `type=DRIVER`, serializer `DriverSerializer` (campos reduzidos).
- `/api/employees/` — só `type=EMPLOYEE`, serializer `EmployeeSerializer` (campos reduzidos).

Para ecrãs “só motoristas” ou “só funcionários”, podes usar estes URLs e **não** misturar tipos na mesma lista; para **CRUD genérico** de qualquer pessoa, mantém `/api/people/`.

---

## 11. Checklist rápido no Angular

1. Serviço com `HttpClient`, `baseUrl + 'people/'`.
2. `getList(params)` → `GET` com `HttpParams` (`company_id`, `type`, `page`).
3. `getOne(id)` → `GET people/{id}/`.
4. `create(body)` → `POST people/` com JSON do §7.
5. `update(id, partial)` → `PATCH people/{id}/`.
6. `delete(id)` → `DELETE people/{id}/` (no backend atual o `BaseViewSet` remove do BD).
7. Formulário reativo: mostrar `license_number` **ou** `employee_code` conforme `type` (alternar com `*ngIf` ou `switch`).
8. Carregar `company` a partir de `GET /api/companies/` para um `<select>` de empresas.
9. Tratar erros 400 com objeto de campo → mensagens na UI.

---

*Gerado com base em `core/models.py` (`Person`), `core/serializers.py` (`PersonSerializer`), `core/viewsets.py` (`PersonViewSet`), `core/filters.py` (`PersonFilter`) e `config/settings.py` (paginação).*
