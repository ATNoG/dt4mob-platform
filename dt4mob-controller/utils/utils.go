package utils

import (
	"bytes"
	"context"
	"crypto"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"io"
	"log/slog"
	"net/http"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	watchv1 "k8s.io/apimachinery/pkg/watch"
	"k8s.io/client-go/kubernetes"

	"github.com/ATNoG/dt4mob/dt4mob-controller/config"
)

func WatchSecret(ctx context.Context, clientset *kubernetes.Clientset, config *config.Config, secretName string) <-chan *corev1.Secret {
	watch, err := clientset.CoreV1().Secrets(config.Namespace).Watch(ctx, metav1.ListOptions{
		FieldSelector: fmt.Sprintf("metadata.name=%s", secretName),
	})

	if err != nil {
		panic(err.Error())
	}

	secretChan := make(chan *corev1.Secret)
	go func(in <-chan watchv1.Event, out chan<- *corev1.Secret) {
		for event := range in {
			if event.Type != watchv1.Added && event.Type != watchv1.Modified {
				continue
			}

			secret := event.Object.(*corev1.Secret)
			out <- secret
		}
	}(watch.ResultChan(), secretChan)

	return secretChan
}

func WatchConfigMap(ctx context.Context, clientset *kubernetes.Clientset, config *config.Config, configMapName string) <-chan *corev1.ConfigMap {
	watch, err := clientset.CoreV1().ConfigMaps(config.Namespace).Watch(ctx, metav1.ListOptions{
		FieldSelector: fmt.Sprintf("metadata.name=%s", configMapName),
	})

	if err != nil {
		panic(err.Error())
	}

	configMapChan := make(chan *corev1.ConfigMap)
	go func(in <-chan watchv1.Event, out chan<- *corev1.ConfigMap) {
		for event := range in {
			if event.Type != watchv1.Added && event.Type != watchv1.Modified {
				continue
			}

			configMap := event.Object.(*corev1.ConfigMap)
			out <- configMap
		}
	}(watch.ResultChan(), configMapChan)

	return configMapChan
}

func PemPrivateKey(key crypto.PrivateKey) ([]byte, error) {
	pkcs8Key, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, err
	}

	keyPem := pem.EncodeToMemory(&pem.Block{
		Type:  "PRIVATE KEY",
		Bytes: pkcs8Key,
	})
	return keyPem, nil
}

func PemCertificateChain(chain [][]byte) []byte {
	chainPem := new(bytes.Buffer)
	for _, cert := range chain {
		pem.Encode(chainPem, &pem.Block{
			Type:  "CERTIFICATE",
			Bytes: cert,
		})
	}
	return chainPem.Bytes()
}

func LogHttpError(msg string, res *http.Response) {
	bodyBytes, err := io.ReadAll(res.Body)
	if err == nil {
		slog.Error(msg, "status", res.StatusCode, "body", string(bodyBytes))
	} else {
		slog.Error(msg, "status", res.StatusCode)
	}
}
