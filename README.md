# Warehouse Management System Simulation - WMSS (MES Layer / Python)

Dự án này là tầng **MES (Manufacturing Execution System)** - "Bộ não Quyết định & Lập kế hoạch" trong hệ thống mô phỏng tự động hóa nhà kho đa ngôn ngữ (Polyglot Microservices).

## 🧩 Vai trò trong hệ thống

Trong kiến trúc 3 tầng (Business → Decision → Execution), MES đảm nhận lớp **Decision Layer** — trả lời cho câu hỏi *"Làm như thế nào?"*:

- **ERP / WMS (Node.js):** Lớp Business — *"Cần làm gì?"* (Ra yêu cầu nghiệp vụ: nhập/xuất hàng).
- **MES (Python):** Lớp Decision — *"Làm như thế nào?"* (Tính toán logic, định tuyến, phân bổ slot, tạo kế hoạch thực thi).
- **AGV Control Service (Golang):** Lớp Execution — *"Thực thi ra sao?"* (Điều khiển AGV realtime dựa trên kế hoạch từ MES).

> **Lưu ý quan trọng:** MES là một dịch vụ **Stateless Calculator**. Nó KHÔNG quản lý nghiệp vụ kho (Business), KHÔNG giám sát trạng thái realtime của AGV. Nó nhận yêu cầu, xử lý toán học/thuật toán phức tạp, tạo ra "Execution Plan" và giao xuống cho tầng Go.

## 🚀 Các Chức Năng Cốt Lõi (Decision Engine)

- **Slot Allocation:** Phân tích và quyết định item nên được cất vào vị trí (slot) nào để tối ưu hóa không gian và thời gian lấy/cất hàng.
- ****Pathfinding (A*):**** Tính toán đường đi ngắn nhất, tối ưu nhất từ điểm A đến điểm B trên lưới (Grid) của nhà kho.
- **Task Generation:** Biên dịch một yêu cầu nghiệp vụ (VD: "Nhập hàng") thành chuỗi các nhiệm vụ thực thi (VD: `MOVE_TO_PICKUP` → `MOVE_TO_STORAGE` → `CHARGE`).
- **Traffic Planning:** Xử lý điều hướng giao thông, tránh va chạm (collision avoidance) khi có nhiều AGV cùng hoạt động.

## 🛠 Công nghệ sử dụng

- **Python 3.10+**: Ngôn ngữ hiện đại, lý tưởng cho xử lý thuật toán, AI và Data.
- **FastAPI**: Framework hiệu suất cao, hỗ trợ tốt AsyncIO.
- **gRPC**: Cung cấp các API tính toán tốc độ cao (Sync) để WMS và Go gọi đến.
- **Kafka**: Lắng nghe (Consume) các yêu cầu từ WMS một cách bất đồng bộ.
- **Redis**: Truy xuất siêu tốc bản đồ kho (Grid layout) và cấu hình dùng chung.

## 🔄 Luồng xử lý chính (Ví dụ: Nhập hàng)

1. **WMS** đẩy yêu cầu nhập hàng vào Kafka.
2. **MES** (Consumer) nhận yêu cầu.
3. **MES** chạy thuật toán **Slot Allocation** để tìm vị trí trống tối ưu.
4. **MES** lấy bản đồ kho từ **Redis** và chạy **A* Pathfinding** để tìm đường đi.
5. **MES** đóng gói kết quả thành một **Execution Plan** (bao gồm Slot, Waypoints, Tasks).
6. **MES** gửi kế hoạch này xuống cho **AGV Control (Go)** qua gRPC để điều khiển Robot thực thi.

## 💻 Hướng dẫn phát triển

### 1. Thiết lập môi trường

```bash
g# Di chuyển vào thư mục MES
cd MES

# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường (Windows)
.venv\Scripts\activate

# Cập nhật build file proto grpc
python build_proto.py

# Copy config env và điền thông tin biến môi trường
cp .env.example .env

# Cài đặt thư viện
pip install -r requirements.txt
```

### 2. Chạy ứng dụng (Development mode)

Sử dụng script chạy chuẩn của dự án (khởi động cả HTTP và gRPC Server):

```bash
python run.py
```

## 🧠 Thuật toán A* (A-Star Pathfinding)

Tầng MES sử dụng thuật toán **A*** làm hạt nhân để tính toán lộ trình cho AGV. A* là một thuật toán tìm kiếm đồ thị phổ biến và cực kỳ hiệu quả cho bài toán tìm đường đi ngắn nhất.

### Nguyên lý hoạt động

Thuật toán đánh giá các Node (ô lưới) dựa trên hàm chi phí tổng quát:
`f(n) = g(n) + h(n)`

Trong đó:

- `f(n)`: Tổng chi phí ước tính để đi từ điểm xuất phát đến đích thông qua Node `n`.
- `g(n)`: Chi phí thực tế đã tiêu tốn để đi từ điểm xuất phát đến Node `n`.
- `h(n)`: **Hàm Heuristic** - Ước lượng chi phí từ Node `n` đến đích. Đây là "bộ não" của thuật toán, giúp A* định hướng tìm kiếm thông minh thay vì mở rộng mù quáng. Trong thực tế, hàm Heuristic còn giúp hệ thống cân nhắc các yếu tố như: vật cản xuất hiện bất ngờ, các lối rẽ, hay luồng giao thông chồng chéo của các AGV khác.

### Hàm Heuristic: Khoảng cách Manhattan

Do đặc thù của hệ thống kho hàng (Grid), AGV chỉ có thể di chuyển theo 4 hướng trực giao (Lên, Xuống, Trái, Phải), hoàn toàn không thể đi chéo. Vì vậy, **Khoảng cách Manhattan** được lựa chọn làm hàm Heuristic vì nó phản ánh chính xác nhất thực tế di chuyển:

`h(n) = |x_n - x_end| + |y_n - y_end|`

Việc sử dụng Manhattan giúp thuật toán chạy nhanh, tối ưu và đảm bảo luôn tìm ra đường đi ngắn nhất tuyệt đối (admissible heuristic).

### Tại sao chọn A* thay vì Dijkstra hay các thuật toán khác?

- **So với Dijkstra:** Dijkstra có xu hướng tìm kiếm mọi hướng như giọt nước loang ra, gây lãng phí tài nguyên tính toán. A* nhờ có hàm Heuristic sẽ được "hút" thẳng về phía đích, giúp tốc độ nhanh hơn vượt trội trong môi trường không gian rộng lớn như kho bãi.
- **So với BFS/DFS:** BFS loang mù quáng và rất chậm. DFS tìm được đường nhưng hiếm khi là đường đi ngắn nhất.
- **Khả năng mở rộng (Collision Avoidance):** Trong tương lai, A* rất dễ tùy biến. Bằng cách cộng thêm "hình phạt" (penalty weight) vào hàm `g(n)` tại những ô đang có AGV khác đi qua, thuật toán sẽ tự động giúp AGV tính toán và tìm một "đường vòng" để tránh kẹt xe.

## 🔮 Tầm nhìn & Định hướng phát triển

Sau khi hệ thống nền tảng với thuật toán A* hoàn thiện, dự án sẽ hướng tới việc tích hợp trí tuệ nhân tạo (AI) để nâng cấp kho hàng thành một hệ thống **Smart Warehouse** thực thụ:

- **AI-Driven Scheduling:** Thay thế việc lập lịch thủ công bằng các mô hình học máy để điều phối hàng ngàn nhiệm vụ cùng lúc, đảm bảo thời gian hoàn thành là ngắn nhất.
- **Slot Optimization (Tối ưu hóa vị trí):** Sử dụng AI để phân tích dữ liệu lịch sử xuất/nhập, từ đó gợi ý vị trí sắp xếp hàng hóa một cách khoa học (ví dụ: hàng hay xuất sẽ để gần lối đi), giúp giảm 30-50% quãng đường di chuyển của AGV.
- **Traffic Intelligence:** Nâng cấp thuật toán tìm đường kết hợp với học sâu (Deep Learning) để AGV có thể tự học cách xử lý các tình huống giao thông phức tạp, tránh ùn tắc và va chạm một cách chủ động.
