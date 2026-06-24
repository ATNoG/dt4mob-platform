package k8s

import (
	"context"
	"fmt"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	watchv1 "k8s.io/apimachinery/pkg/watch"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

func NewClient() (*kubernetes.Clientset, error) {
	loadingRules := clientcmd.NewDefaultClientConfigLoadingRules()
	configOverrides := &clientcmd.ConfigOverrides{}
	kubeConfig := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(loadingRules, configOverrides)

	clientConfig, err := kubeConfig.ClientConfig()
	if err != nil {
		clientConfig, err = rest.InClusterConfig()
		if err != nil {
			return nil, fmt.Errorf("kubeconfig and in-cluster config failed: %w", err)
		}
	}

	return kubernetes.NewForConfig(clientConfig)
}

func ReadSecret(ctx context.Context, clientset *kubernetes.Clientset, namespace, name string) (*corev1.Secret, error) {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	return clientset.CoreV1().Secrets(namespace).Get(ctx, name, metav1.GetOptions{})
}

func WatchSecret(ctx context.Context, clientset *kubernetes.Clientset, namespace, name string) (<-chan *corev1.Secret, error) {
	watch, err := clientset.CoreV1().Secrets(namespace).Watch(ctx, metav1.ListOptions{
		FieldSelector: fmt.Sprintf("metadata.name=%s", name),
	})
	if err != nil {
		return nil, err
	}

	secretChan := make(chan *corev1.Secret)
	go func() {
		defer watch.Stop()
		for event := range watch.ResultChan() {
			if event.Type != watchv1.Added && event.Type != watchv1.Modified {
				continue
			}
			secret := event.Object.(*corev1.Secret)
			secretChan <- secret
		}
	}()

	return secretChan, nil
}
