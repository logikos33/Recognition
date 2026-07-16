# Build do custom bbox parser YOLOX pro DeepStream nvinfer (task-088).
#
# Uso no box (Jetson, DeepStream 7.1):
#   make
# Gera libnvdsparsebbox_yolox.so — referenciar no config do nvinfer:
#   parse-bbox-func-name=NvDsInferParseCustomYolox
#   custom-lib-path=/caminho/libnvdsparsebbox_yolox.so
#   cluster-mode=2   (NMS — o nvinfer faz o clustering; o parser só decodifica)

DEEPSTREAM_DIR ?= /opt/nvidia/deepstream/deepstream-7.1
CUDA_DIR ?= /usr/local/cuda
CXX := g++

# NvInfer.h (puxado por nvdsinfer_custom_impl.h) inclui cuda_runtime_api.h →
# precisa do include do CUDA toolkit.
CXXFLAGS := -Wall -Wextra -std=c++14 -fPIC -shared \
            -I$(DEEPSTREAM_DIR)/sources/includes \
            -I$(CUDA_DIR)/include

TARGET := libnvdsparsebbox_yolox.so
SRC := nvdsparsebbox_yolox.cpp

$(TARGET): $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $<

.PHONY: clean
clean:
	rm -f $(TARGET)
