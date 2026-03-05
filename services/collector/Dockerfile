# 使用多阶段构建减小镜像大小
FROM golang:1.21-alpine AS builder

# 设置工作目录
WORKDIR /app

# 安装 git (某些依赖需要)
RUN apk add --no-cache git

# 复制 go mod 文件
COPY go.mod go.sum ./

# 下载依赖
RUN go mod download

# 复制源代码
COPY *.go ./

# 构建应用
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o collector .

# 使用轻量级基础镜像
FROM alpine:latest

# 安装 ca-certificates 用于 HTTPS 请求
RUN apk --no-cache add ca-certificates

WORKDIR /root/

# 从构建阶段复制二进制文件
COPY --from=builder /app/collector .

# 暴露端口 (如果需要 HTTP 接口)
EXPOSE 8080

# 运行应用
CMD ["./collector"]