from rest_framework.viewsets import ModelViewSet
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Pack, SubscriptionHistory, Order
from .serializers import PackSerializer, SubscriptionHistorySerializer, OrderSerializer
from .permissions import IsAdminOrReadOnly
from .ifthenpay_service import IfThenPayService
import logging

logger = logging.getLogger(__name__)

class PackViewSet(ModelViewSet):
    queryset = Pack.objects.all()
    serializer_class = PackSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, "role", None) == "admin":
            return Pack.objects.all()
        return Pack.objects.filter(active=True)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, pk=None):
        """
        Subscribe a professional to a pack.
        Supports MultiBanco and MB WAY payment methods.
        Hours will be added AFTER payment is confirmed.
        
        Body Parameters:
        - payment_method: 'multibanco' or 'mbway' (required)
        - phone_number: Required for MB WAY (format: 351#912345678)
        """
        pack = self.get_object()
        user = request.user

        # Check if user is a professional
        if user.role not in ['professional', 'teacher']:
            return Response(
                {"error": "Only professionals can subscribe to packs."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if pack is active
        if not pack.active:
            return Response(
                {"error": "This pack is not available for subscription."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get payment method from request
        payment_method = request.data.get('payment_method', 'multibanco').lower()
        
        if payment_method not in ['multibanco', 'mbway', 'creditcard']:
            return Response(
                {"error": "Invalid payment method. Choose 'multibanco', 'mbway', or 'creditcard'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For MB WAY, phone number is required
        phone_number = request.data.get('phone_number', '')
        if payment_method == 'mbway' and not phone_number:
            return Response(
                {"error": "Phone number is required for MB WAY payments. Format: 351#912345678"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create order with Pendente status
        order = Order.objects.create(
            user=user,
            pack=pack,
            amount=pack.price,
            payment_method=payment_method,
            payment_status='Pendente',
            mbway_phone=phone_number if payment_method == 'mbway' else None
        )
        
        # Generate order ID after creation (needs pk)
        from .ifthenpay_service import IfThenPayService
        ifthenpay_service = IfThenPayService()
        
        # Use different max lengths for different payment methods
        max_length = 15 if payment_method in ['mbway', 'creditcard'] else 25
        order.order_id = ifthenpay_service.generate_order_id(order, max_length=max_length)
        order.save()
        
        try:
            if payment_method == 'multibanco':
                return self._process_multibanco_payment(order, user, ifthenpay_service, request)
            elif payment_method == 'mbway':
                return self._process_mbway_payment(order, user, ifthenpay_service, phone_number, request)
            elif payment_method == 'creditcard':
                return self._process_creditcard_payment(order, user, ifthenpay_service, request)
                
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            order.delete()
            return Response({
                "error": "Failed to create payment. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_multibanco_payment(self, order, user, ifthenpay_service, request):
        """Process MultiBanco payment"""
        result = ifthenpay_service.create_payment_reference(order, user, expiry_days=3)
        
        if result['success']:
            # Update order with payment reference details
            order.mb_key = ifthenpay_service.mb_key
            order.mb_entity = result['entity']
            order.mb_reference = result['reference']
            order.request_id = result['request_id']
            order.expiry_date = result['expiry_date']
            order.save()
            
            # Send email with payment reference
            self.send_multibanco_email(user, order, result)
            
            # Build callback URL for testing
            callback_url = (
                f"{request.scheme}://{request.get_host()}/api/subscriptions/callback/ifthenpay/"
                f"?key={result['entity']}&order_id={order.order_id}&amount={result['amount']}"
                f"&reference={result['reference']}&entity={result['entity']}"
            )
            
            return Response({
                "message": "Order created successfully. Please complete the payment.",
                "payment_method": "multibanco",
                "order": OrderSerializer(order).data,
                "payment_details": {
                    "entity": result['entity'],
                    "reference": result['reference'],
                    "amount": f"€{float(result['amount']):.2f}",
                    "expiry_date": result.get('expiry_date_display') or result.get('expiry_date'),
                },
                "callback_url_for_testing": callback_url
            }, status=status.HTTP_201_CREATED)
        else:
            order.delete()
            return Response({
                "error": f"Failed to generate payment reference: {result.get('error')}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_mbway_payment(self, order, user, ifthenpay_service, phone_number, request):
        """Process MB WAY payment"""
        result = ifthenpay_service.create_mbway_payment(order, user, phone_number)
        
        if result['success']:
            # Update order with MB WAY details
            order.request_id = result['request_id']
            order.save()
            
            # Send email notification
            self.send_mbway_email(user, order, phone_number)
            
            # Build callback URL for testing
            callback_url = (
                f"{request.scheme}://{request.get_host()}/api/subscriptions/callback/ifthenpay/"
                f"?key={ifthenpay_service.mbway_key}&order_id={order.order_id}&amount={result['amount']}"
                f"&requestId={result['request_id']}"
            )
            
            return Response({
                "message": "MB WAY payment request sent. Please approve on your phone within 4 minutes.",
                "payment_method": "mbway",
                "order": OrderSerializer(order).data,
                "payment_details": {
                    "phone_number": phone_number,
                    "amount": f"€{float(result['amount']):.2f}",
                    "status": result['status'],
                    "request_id": result['request_id'],
                    "timeout": "4 minutes"
                },
                "callback_url_for_testing": callback_url
            }, status=status.HTTP_201_CREATED)
        else:
            order.delete()
            return Response({
                "error": f"Failed to initiate MB WAY payment: {result.get('error')}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_creditcard_payment(self, order, user, ifthenpay_service, request):
        """Process Credit Card payment"""
        # Build callback URLs
        base_url = request.build_absolute_uri('/').rstrip('/')
        success_url = f"{base_url}/api/subscriptions/callback/creditcard/success/"
        error_url = f"{base_url}/api/subscriptions/callback/creditcard/error/"
        cancel_url = f"{base_url}/api/subscriptions/callback/creditcard/cancel/"
        
        result = ifthenpay_service.create_creditcard_payment(
            order, success_url, error_url, cancel_url, language='pt'
        )
        
        if result['success']:
            # Update order with Credit Card details
            order.request_id = result['request_id']
            order.ccard_payment_url = result['payment_url']
            order.save()
            
            # Send email notification
            self.send_creditcard_email(user, order, result['payment_url'])
            
            return Response({
                "message": "Credit Card payment page ready. Redirect user to payment_url.",
                "payment_method": "creditcard",
                "order": OrderSerializer(order).data,
                "payment_details": {
                    "payment_url": result['payment_url'],
                    "request_id": result['request_id'],
                    "amount": f"€{float(order.amount):.2f}",
                }
            }, status=status.HTTP_201_CREATED)
        else:
            order.delete()
            return Response({
                "error": f"Failed to initiate Credit Card payment: {result.get('error')}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_multibanco_email(self, user, order, payment_details):
        """Send email with MultiBanco payment reference"""
        subject = f"Referência de Pagamento - {order.pack.title}"
        
        # Use display date if available, otherwise try to format the datetime
        expiry_display = payment_details.get('expiry_date_display')
        if not expiry_display and payment_details.get('expiry_date'):
            expiry_date = payment_details['expiry_date']
            if expiry_date:
                expiry_display = expiry_date.strftime('%d-%m-%Y') if hasattr(expiry_date, 'strftime') else str(expiry_date)
            else:
                expiry_display = 'Sem expiração'
        
        message = f"""
Olá {user.full_name},

Obrigado pela sua subscrição ao plano "{order.pack.title}".

Para concluir o seu pagamento, utilize os seguintes dados:

Entidade: {payment_details['entity']}
Referência: {payment_details['reference']}
Valor: €{float(payment_details['amount']):.2f}

Data de Expiração: {expiry_display or 'Sem expiração'}

Pode efetuar o pagamento em qualquer Multibanco, Homebanking ou aplicação MB WAY.

Após a confirmação do pagamento, as suas horas serão automaticamente adicionadas à sua conta.

ID do Pedido: {order.order_id}

Obrigado,
Equipa YourselfPilates
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Payment reference email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send payment reference email: {str(e)}")
    
    def send_mbway_email(self, user, order, phone_number):
        """Send email notification for MB WAY payment"""
        subject = f'Pedido de Pagamento MB WAY - {order.pack.title}'
        message = f"""
Olá {user.full_name},

Foi enviado um pedido de pagamento MB WAY para o seu telemóvel!

Detalhes do Pagamento:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pack: {order.pack.title}
Valor: €{float(order.amount):.2f}
Telemóvel: {phone_number.replace('#', ' ')}
Validade: 4 minutos
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Por favor, abra a app MB WAY no seu telemóvel e aprove o pagamento.

Após a confirmação do pagamento, as horas do pack ({order.pack.total_hours} horas) serão automaticamente adicionadas à sua conta.

ID do Pedido: {order.order_id}

Obrigado,
Equipa YourselfPilates
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"MB WAY payment email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send MB WAY payment email: {str(e)}")
    
    def send_creditcard_email(self, user, order, payment_url):
        """Send email notification for Credit Card payment"""
        subject = f'Pagamento por Cartão de Crédito - {order.pack.title}'
        message = f"""
Olá {user.full_name},

A sua página de pagamento por cartão de crédito está pronta!

Detalhes do Pagamento:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pack: {order.pack.title}
Valor: €{float(order.amount):.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Por favor, clique no link abaixo para completar o pagamento:
{payment_url}

Após a confirmação do pagamento, as horas do pack ({order.pack.total_hours} horas) serão automaticamente adicionadas à sua conta.

ID do Pedido: {order.order_id}

Obrigado,
Equipa YourselfPilates
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            logger.info(f"Credit Card payment email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send Credit Card payment email: {str(e)}")


class OrderViewSet(ModelViewSet):
    """ViewSet for managing payment orders"""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter orders based on user role"""
        user = self.request.user
        
        # Admin can see all orders
        if user.role == 'admin':
            return Order.objects.all().order_by('-created_at')
        
        # Professionals/teachers can only see their own orders
        if user.role in ['professional', 'teacher']:
            return Order.objects.filter(user=user).order_by('-created_at')
        
        return Order.objects.none()
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def check_mbway_status(self, request, pk=None):
        """
        Check MB WAY payment status for a specific order.
        Only works for MB WAY payments.
        """
        order = self.get_object()
        
        # Check if user owns this order or is admin
        if order.user != request.user and request.user.role != 'admin':
            return Response(
                {"error": "You don't have permission to check this order."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if this is a MB WAY payment
        if order.payment_method != 'mbway':
            return Response(
                {"error": "This endpoint only works for MB WAY payments."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already paid
        if order.payment_status == 'Pago':
            return Response({
                "status": "paid",
                "message": "Payment has already been confirmed.",
                "order": OrderSerializer(order).data
            })
        
        # Check if order has request_id
        if not order.request_id:
            return Response(
                {"error": "No request_id found for this order."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check payment status with IfThenPay
        from .ifthenpay_service import IfThenPayService
        ifthenpay_service = IfThenPayService()
        
        try:
            result = ifthenpay_service.check_mbway_status(order.request_id, order.amount)
            
            return Response({
                "order_id": order.order_id,
                "payment_status": order.payment_status,
                "mbway_status": result['status'],
                "is_paid": result['is_paid'],
                "is_rejected": result['is_rejected'],
                "is_expired": result['is_expired'],
                "message": result['message']
            })
            
        except Exception as e:
            logger.error(f"Error checking MB WAY status: {str(e)}")
            return Response({
                "error": "Failed to check payment status. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Callback endpoint for IfThenPay payment notifications
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

@csrf_exempt
def ifthenpay_callback(request):
    """
    Webhook endpoint to receive payment confirmation from IfThenPay.
    This endpoint will be called by IfThenPay when a payment is completed.
    
    Expected parameters (will vary based on IfThenPay callback format):
    - order_id or reference
    - amount
    - status
    """
    if request.method != 'GET' and request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    try:
        # Get parameters from request (adjust based on actual IfThenPay callback format)
        params = request.GET if request.method == 'GET' else request.POST
        
        logger.info(f"IfThenPay callback received: {params}")
        
        # Extract relevant data (adjust field names based on actual callback)
        order_id = params.get('id') or params.get('order_id')
        reference = params.get('referencia') or params.get('reference')
        amount = params.get('valor') or params.get('amount')
        
        if not order_id and not reference:
            logger.error("Missing order_id or reference in callback")
            return HttpResponse('Missing parameters', status=400)
        
        # Find the order
        order = None
        if order_id:
            order = Order.objects.filter(order_id=order_id).first()
        if not order and reference:
            order = Order.objects.filter(mb_reference=reference).first()
        
        if not order:
            logger.error(f"Order not found: order_id={order_id}, reference={reference}")
            return HttpResponse('Order not found', status=404)
        
        # Check if already paid
        if order.payment_status == 'Pago':
            logger.info(f"Order {order.order_id} already paid")
            return HttpResponse('OK', status=200)
        
        # Update order status
        order.payment_status = 'Pago'
        order.paid_at = timezone.now()
        order.save()
        
        # Add hours to user account
        user = order.user
        # user.remaining_hours += order.pack.total_hours
        user.subscribed_pack = order.pack
        user.subscription_date = timezone.now()
        user.save()
        
        # Create subscription history
        SubscriptionHistory.objects.create(
            user=user,
            pack=order.pack,
            hours_added=order.pack.total_hours
        )
        
        # Send confirmation email
        send_payment_confirmation_email(user, order)
        
        logger.info(f"Payment confirmed for order {order.order_id}")
        return HttpResponse('OK', status=200)
        
    except Exception as e:
        logger.error(f"Error processing IfThenPay callback: {str(e)}")
        return HttpResponse('Internal server error', status=500)


def send_payment_confirmation_email(user, order):
    """Send email confirming payment was received"""
    subject = f"Pagamento Confirmado - {order.pack.title}"
    message = f"""
            Olá {user.full_name},

            O seu pagamento foi confirmado com sucesso!

            Plano: {order.pack.title}
            Valor: €{float(order.amount):.2f}
            Horas adicionadas: {order.pack.total_hours}
            Horas disponíveis: {float(user.remaining_hours)}

            Pode agora utilizar as suas horas para reservar aulas.

            ID do Pedido: {order.order_id}

            Obrigado pela sua preferência!
            Equipa YourselfPilates
            """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Payment confirmation email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {str(e)}")


# Credit Card callback endpoints
@csrf_exempt
def creditcard_success_callback(request):
    """
    Callback endpoint for successful Credit Card payment
    Parameters: id, amount, requestId, sk (signature key)
    """
    try:
        params = request.GET if request.method == 'GET' else request.POST
        logger.info(f"Credit Card SUCCESS callback received: {params}")
        
        order_id = params.get('id')
        amount = params.get('amount')
        request_id = params.get('requestId')
        signature_key = params.get('sk')
        
        if not all([order_id, amount, request_id, signature_key]):
            logger.error("Missing parameters in success callback")
            return HttpResponse('Missing parameters', status=400)
        
        # Find the order
        order = Order.objects.filter(order_id=order_id).first()
        if not order:
            logger.error(f"Order not found: {order_id}")
            return HttpResponse('Order not found', status=404)
        
        # Verify signature
        from .ifthenpay_service import IfThenPayService
        ifthenpay_service = IfThenPayService()
        
        if not ifthenpay_service.verify_creditcard_signature(order_id, amount, request_id, signature_key):
            logger.error(f"Invalid signature for order {order_id}")
            return HttpResponse('Invalid signature', status=403)
        
        # Check if already paid
        if order.payment_status == 'Pago':
            logger.info(f"Order {order.order_id} already paid")
            return HttpResponse('OK - Already paid', status=200)
        
        # Update order
        order.payment_status = 'Pago'
        order.paid_at = timezone.now()
        order.ccard_signature_key = signature_key
        order.save()
        
        # Add hours to user
        user = order.user
        user.remaining_hours += order.pack.total_hours
        user.subscribed_pack = order.pack
        user.subscription_date = timezone.now()
        user.save()
        
        # Create subscription history
        SubscriptionHistory.objects.create(
            user=user,
            pack=order.pack,
            hours_added=order.pack.total_hours
        )
        
        # Send confirmation email
        send_payment_confirmation_email(user, order)
        
        logger.info(f"Credit Card payment confirmed for order {order.order_id}")
        
        # Get frontend URL from settings
        import os
        frontend_url = os.getenv('FRONTEND_URL', '/')
        
        # Redirect to a success page (you can customize this)
        return HttpResponse(f"""
            <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">✓ Pagamento Confirmado!</h1>
                <p>O seu pagamento foi processado com sucesso.</p>
                <p>Pedido: {order.order_id}</p>
                <p>Valor: €{float(order.amount):.2f}</p>
                <p>As suas horas foram adicionadas à sua conta.</p>
                <p><a href="{frontend_url}">Voltar ao início</a></p>
            </body>
            </html>
        """, content_type='text/html')
        
    except Exception as e:
        logger.error(f"Error processing Credit Card success callback: {str(e)}")
        return HttpResponse('Internal server error', status=500)


@csrf_exempt
def creditcard_error_callback(request):
    """
    Callback endpoint for failed Credit Card payment
    Parameters: id, amount, requestId
    """
    try:
        params = request.GET if request.method == 'GET' else request.POST
        logger.info(f"Credit Card ERROR callback received: {params}")
        
        order_id = params.get('id')
        
        if order_id:
            order = Order.objects.filter(order_id=order_id).first()
            if order:
                order.payment_status = 'Cancelado'
                order.save()
                logger.info(f"Order {order_id} marked as Cancelado (error)")
        
        # Get frontend URL from settings
        import os
        frontend_url = os.getenv('FRONTEND_URL', '/')
        
        return HttpResponse(f"""
            <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: red;">✗ Erro no Pagamento</h1>
                <p>Ocorreu um erro ao processar o seu pagamento.</p>
                <p>Por favor, tente novamente.</p>
                <p><a href="{frontend_url}">Voltar ao início</a></p>
            </body>
            </html>
        """, content_type='text/html')
        
    except Exception as e:
        logger.error(f"Error processing Credit Card error callback: {str(e)}")
        return HttpResponse('Internal server error', status=500)


@csrf_exempt
def creditcard_cancel_callback(request):
    """
    Callback endpoint for cancelled Credit Card payment
    Parameters: id, amount, requestId
    """
    try:
        params = request.GET if request.method == 'GET' else request.POST
        logger.info(f"Credit Card CANCEL callback received: {params}")
        
        order_id = params.get('id')
        
        if order_id:
            order = Order.objects.filter(order_id=order_id).first()
            if order:
                order.payment_status = 'Cancelado'
                order.save()
                logger.info(f"Order {order_id} marked as Cancelado (user cancelled)")
        
        # Get frontend URL from settings
        import os
        frontend_url = os.getenv('FRONTEND_URL', '/')
        
        return HttpResponse(f"""
            <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: orange;">⚠ Pagamento Cancelado</h1>
                <p>O pagamento foi cancelado.</p>
                <p>Se mudou de ideias, pode tentar novamente.</p>
                <p><a href="{frontend_url}">Voltar ao início</a></p>
            </body>
            </html>
        """, content_type='text/html')
        
    except Exception as e:
        logger.error(f"Error processing Credit Card cancel callback: {str(e)}")
        return HttpResponse('Internal server error', status=500)
