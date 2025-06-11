from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import datetime
import requests
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from dateutil import parser 
from dateutil.parser import isoparse

def is_logged_in(request):
    return bool(request.session.get('token'))

# Create your views here.
def index(request):
    return render(request,'frontend/index.html',context={
        'year': datetime.datetime.now().year,
        'is_logged_in': is_logged_in(request),
        'title' : 'Topsis Home',
        })

def dashboard(request):
    if not request.session.get('token'):
        return redirect('frontend:login')

    recent_history = []
    error_message = None

    try:
        # Mengambil logika dari view topsis_history Anda
        response = requests.get(
            'https://benewtopsis-production.up.railway.app/api/topsis/history',
            cookies={'Authorization': request.session.get('token')}
        )
        
        if response.status_code == 200:
            history_data = response.json().get('data', [])
            
            # --- Bagian Penting: Transformasi & Pengurutan ---
            
            # 1. Parsing tanggal agar bisa diurutkan
            for item in history_data:
                # Mengubah string tanggal menjadi objek datetime
                item['parsed_date'] = parser.isoparse(item.get('created_at', ''))

            # 2. Mengurutkan history dari yang paling baru (descending)
            sorted_history = sorted(history_data, key=lambda x: x['parsed_date'], reverse=True)
            
            # 3. Ambil 5 item teratas untuk ditampilkan di dashboard
            recent_history = sorted_history[:5]

        else:
            # Jika API error, tampilkan pesan di dashboard (opsional)
            error_message = f'Tidak dapat memuat riwayat: Status {response.status_code}'

    except Exception as e:
        error_message = f'Terjadi kesalahan saat menghubungi server: {str(e)}'

    context = {
        'title': 'Dashboard',
        'year': datetime.datetime.now().year,
        'is_logged_in': is_logged_in(request),
        'recent_history': recent_history, # Kirim data history ke template
        'api_error': error_message # Kirim pesan error jika ada
    }
    return render(request, 'frontend/dashboard.html', context)

def signup(request):
    if request.session.get('token'):
        return redirect('frontend:dashboard')
    if request.method == 'POST' :
        nama_lengkap = request.POST.get('nama_lengkap')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        payload = {
                'nama_lengkap' : nama_lengkap,
                'email' : email,
                'password' : password,
                'confirm_password' : confirm_password
                }
        try :
            response = requests.post('https://benewtopsis-production.up.railway.app/api/signup', json=payload)
            if response.status_code == 200 :
                json_response = response.json()
                message = json_response.get('message', 'Succes')
            else:
                message = f'Error {response.status_code}'
        except Exception as e:
            message = f'terjadi Error{e}'
        return render(request, 'frontend/signup.html', context={
            'title' : 'signup',
            'message' : message,
            'year': datetime.datetime.now().year,
            'is_logged_in': is_logged_in(request)
            })
    else:
        return render(request, 'frontend/signup.html', context={
            'title' : 'signup',
            'year': datetime.datetime.now().year,
        'is_logged_in': is_logged_in(request)
            })

def login(request):
    if request.session.get('token'):
        return redirect('frontend:dashboard')
    if request.method == 'POST' :
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        payload = {
                'email' : email,
                'password' : password,
                'confirm_password' : confirm_password
                } 
        try:
            response = requests.post(
                'https://benewtopsis-production.up.railway.app/api/login',
                json=payload
            )
            if response.status_code == 200 :
                token = response.cookies.get('Authorization')
                if token:
                    request.session['token'] = token
                    return redirect('frontend:dashboard')
                else:
                    message = 'Login Gagal'
            else:
                message = f'login gagal: {response.status_code}'
        except Exception as e:
            message = f'Error : {e}'
        return render(request, 'frontend/login.html', context={
            'title' : 'login',
            'message' : message,
            'year': datetime.datetime.now().year,
            'is_logged_in': is_logged_in(request)
            })
    return render(request, 'frontend/login.html', context={
        'title' : 'login',
        'year': datetime.datetime.now().year,
        'is_logged_in': is_logged_in(request)
        })

def logout(request):
    if request.session.get('token'):
        del request.session['token']
    return redirect('frontend:login')

def topsis_calculate(request):
    if not request.session.get('token'):
        return redirect('frontend:login')
    
    if request.method == 'POST':
        try:
            # Get form data
            criteria_names = request.POST.getlist('criteria_name[]')
            criteria_weights = request.POST.getlist('criteria_weight[]')
            criteria_types = request.POST.getlist('criteria_type[]')
            
            alternative_names = request.POST.getlist('alternative_name[]')
            
            # Build criteria
            criteria = []
            for i, name in enumerate(criteria_names):
                if name:  # Only add non-empty criteria
                    criteria.append({
                        'name': name,
                        'weight': float(criteria_weights[i]),
                        'type': criteria_types[i]
                    })
            
            # Build alternatives
            alternatives = []
            for i, alt_name in enumerate(alternative_names):
                if alt_name:  # Only add non-empty alternatives
                    values = {}
                    for j, crit_name in enumerate(criteria_names):
                        if crit_name:
                            field_name = f'alternative_{i}_{crit_name}'
                            value = request.POST.get(field_name)
                            if value:
                                values[crit_name] = float(value)
                    
                    if values:  # Only add if has values
                        alternatives.append({
                            'name': alt_name,
                            'values': values
                        })
            
            # Prepare payload for calculation
            payload = {
                'criteria': criteria,
                'alternatives': alternatives
            }
            
            # Store original data for saving later
            request.session['original_input'] = {
                'criteria': criteria,
                'alternatives': alternatives
            }
            
            # Send request to API
            response = requests.post(
                'https://benewtopsis-production.up.railway.app/api/topsis',
                json=payload,
                cookies={'Authorization': request.session.get('token')} 
            )
            
            if response.status_code == 200:
                result_data = response.json()
                # Store result in session for saving later
                request.session['topsis_result'] = result_data
                return render(request, 'frontend/topsis_result.html', {
                    'title': 'TOPSIS Result',
                    'result': result_data,
                    'original_criteria': criteria,
                    'original_alternatives': alternatives,
                    'year': datetime.datetime.now().year,
                    'is_logged_in': is_logged_in(request)
                })
            else:
                error_message = f'Error calculating TOPSIS: {response.status_code}'
                return render(request, 'frontend/topsis.html', {
                    'title': 'TOPSIS Calculator',
                    'error': error_message,
                    'year': datetime.datetime.now().year,
                    'is_logged_in': is_logged_in(request)
                })
                
        except Exception as e:
            error_message = f'Error: {str(e)}'
            return render(request, 'frontend/topsis.html', {
                'title': 'TOPSIS Calculator',
                'error': error_message,
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            })
    
    return render(request, 'frontend/topsis.html', {
        'title': 'TOPSIS Calculator',
        'year': datetime.datetime.now().year,
        'is_logged_in': is_logged_in(request)
    })

def topsis_save(request):
    if not request.session.get('token'):
        return redirect('frontend:login')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('calculation_name')
            result_data = request.session.get('topsis_result')
            original_input = request.session.get('original_input')
            
            if not result_data or not original_input:
                return JsonResponse({'success': False, 'message': 'No calculation result found'})
            
            # Transform original input to match raw_input format
            criteria_dict = {}
            weights = []
            alternatives_list = []
            values_matrix = []
            
            # Build criteria dictionary and weights array
            for criterion in original_input['criteria']:
                criteria_dict[criterion['name']] = criterion['type']
                weights.append(criterion['weight'])
            
            # Build alternatives list and values matrix
            for alternative in original_input['alternatives']:
                alternatives_list.append(alternative['name'])
                alt_values = []
                for criterion in original_input['criteria']:
                    alt_values.append(alternative['values'][criterion['name']])
                values_matrix.append(alt_values)
            
            # Prepare payload for save with raw_input structure
            payload = {
                'name': name,
                'data': result_data.get('data', {}),
                'raw_input': {
                    'alternatives': alternatives_list,
                    'criteria': criteria_dict,
                    'values': values_matrix,
                    'weights': weights
                }
            }
            
            response = requests.post(
                'https://benewtopsis-production.up.railway.app/api/topsis/save',
                json=payload,
                cookies={'Authorization': request.session.get('token')}
            )
            
            if response.status_code == 200:
                result = response.json()
                # Clear session results after saving
                if 'topsis_result' in request.session:
                    del request.session['topsis_result']
                if 'original_input' in request.session:
                    del request.session['original_input']
                return JsonResponse({
                    'success': True, 
                    'message': result.get('message', 'Saved successfully'),
                    'calculation_id': result.get('calculation_id')
                })
            else:
                return JsonResponse({'success': False, 'message': f'Error saving: {response.status_code}'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def topsis_history(request):
    if not request.session.get('token'):
        return redirect('frontend:login')
    
    try:
        response = requests.get(
            'https://benewtopsis-production.up.railway.app/api/topsis/history',
            cookies={'Authorization': request.session.get('token')}
        )
        print("URL API:", 'https://benewtopsis-production.up.railway.app/api/topsis/history')  # Debug
        print("Token Terkirim:", request.session.get('token'))        # Debug
        print("Status Respons:", response.status_code)                # Debug
        print("Konten Respons:", response.text)                       # Debug
        
        if response.status_code == 200:
            history_data = response.json()
            # Transformasi data untuk sesuai dengan template
            transformed_history = [
                {
                    'ID': item.get('id', ''),  # Ubah 'id' menjadi 'ID'
                    'Name': item.get('name', 'Tanpa Nama'),
                    'CreatedAt': item.get('created_at', ''),
                    'UpdatedAt': item.get('updated_at', ''),
                    'IdealSolutions': [
                        {
                            'CriteriaName': ideal.get('criteria_name', ''),
                            'IdealPositive': ideal.get('ideal_positive', 0),
                            'IdealNegative': ideal.get('ideal_negative', 0)
                        } for ideal in item.get('ideal_solutions', [])
                    ],
                    'Alternatives': [
                        {
                            'Name': alt.get('name', ''),
                            'ClosenessValue': alt.get('closeness_value', 0),
                            'Rank': alt.get('rank', 0)
                        } for alt in item.get('alternatives', [])
                    ]
                } for item in history_data.get('data', [])
            ]
            print("History yang Ditransformasi:", transformed_history)  # Debug
            return render(request, 'frontend/topsis_history.html', {
                'title': 'TOPSIS History',
                'history': transformed_history,
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            })
        else:
            error_message = f'Error mengambil history: {response.status_code}'
            print("Pesan Error:", error_message)  # Debug
            return render(request, 'frontend/topsis_history.html', {
                'title': 'TOPSIS History',
                'error': error_message,
                'history': [],
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            })
    except Exception as e:
        error_message = f'Error: {str(e)}'
        print("Eksepsi:", error_message)  # Debug
        return render(request, 'frontend/topsis_history.html', {
            'title': 'TOPSIS History',
            'error': error_message,
            'history': [],
            'year': datetime.datetime.now().year,
            'is_logged_in': is_logged_in(request)
        })


# GANTI FUNGSI LAMA ANDA DENGAN YANG INI SECARA KESELURUHAN
def topsis_detail(request, calculation_id):
    if not request.session.get('token'):
        return redirect('frontend:login')
    
    try:
        response = requests.get(
            f'https://benewtopsis-production.up.railway.app/api/topsis/{int(calculation_id)}',
            cookies={'Authorization': request.session.get('token')}
        )
        
        if response.status_code == 200:
            detail_data = response.json()
            detail = detail_data.get('data', {})

            # --- TAMBAHAN: Konversi string tanggal menjadi objek datetime ---
            # Ini akan membuat filter |date di template berfungsi
            if detail.get('created_at'):
                detail['created_at'] = isoparse(detail['created_at'])
            if detail.get('updated_at'):
                detail['updated_at'] = isoparse(detail['updated_at'])
            # --- AKHIR TAMBAHAN ---

            # Kode persiapan data lainnya dari respons sebelumnya
            raw_data = detail.get('raw_data', {})
            criteria_dict = raw_data.get('criteria', {})
            weights_list = raw_data.get('weights', [])
            combined_criteria = []
            for i, (name, type) in enumerate(criteria_dict.items()):
                weight = weights_list[i] if i < len(weights_list) else 'N/A'
                combined_criteria.append({'name': name, 'type': type, 'weight': weight})

            alternatives_list = raw_data.get('alternatives', [])
            values_matrix = raw_data.get('values', [])
            original_matrix = []
            for i, alt_name in enumerate(alternatives_list):
                values = values_matrix[i] if i < len(values_matrix) else []
                original_matrix.append({'name': alt_name, 'values': values})

            context = {
                'title': f'Detail: {detail.get("name", "N/A")}',
                'detail': detail, # 'created_at' & 'updated_at' di sini sudah menjadi objek datetime
                'combined_criteria': combined_criteria,
                'original_matrix': original_matrix,
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            }
            return render(request, 'frontend/topsis_detail.html', context)
        
        else:
            error_message = f'Error mengambil detail: {response.status_code}'
            return render(request, 'frontend/topsis_detail.html', {'title': 'Error', 'error': error_message})
            
    except Exception as e:
        error_message = f'Error: {str(e)}'
        return render(request, 'frontend/topsis_detail.html', {'title': 'Error', 'error': error_message})

def topsis_edit(request, calculation_id):
    """View untuk edit perhitungan TOPSIS"""
    if not request.session.get('token'):
        return redirect('frontend:login')
    
    try:
        # Fetch data perhitungan yang akan diedit
        response = requests.get(
            f'https://benewtopsis-production.up.railway.app/api/topsis/{int(calculation_id)}',
            cookies={'Authorization': request.session.get('token')}
        )
        
        if response.status_code == 200:
            detail_data = response.json()
            topsis_data = detail_data.get('data', {})
            
            # Convert data ke format yang sesuai untuk form
            alternatives_data = []
            raw_data = topsis_data.get('raw_data', {})
            
            # Gabungkan data alternatives dengan values untuk editing
            for i, alt_name in enumerate(raw_data.get('alternatives', [])):
                alt_data = {
                    'name': alt_name,
                    'values': []
                }
                
                # Ambil values untuk alternatif ini
                if i < len(raw_data.get('values', [])):
                    values = raw_data['values'][i]
                    criteria_names = list(raw_data.get('criteria', {}).keys())
                    
                    for j, value in enumerate(values):
                        if j < len(criteria_names):
                            alt_data['values'].append({
                                'criteria_name': criteria_names[j],
                                'value': value
                            })
                
                alternatives_data.append(alt_data)
            
            context = {
                'title': 'Edit TOPSIS Calculation',
                'calculation_id': calculation_id,
                'topsis_data': topsis_data,
                'alternatives_data': alternatives_data,
                'criteria': raw_data.get('criteria', {}),
                'weights': raw_data.get('weights', []),
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            }
            
            return render(request, 'frontend/topsis_edit.html', context)
        else:
            error_message = f'Error fetching data: {response.status_code}'
            return render(request, 'frontend/topsis_edit.html', {
                'title': 'Edit TOPSIS Calculation',
                'error': error_message,
                'year': datetime.datetime.now().year,
                'is_logged_in': is_logged_in(request)
            })
            
    except Exception as e:
        error_message = f'Error: {str(e)}'
        return render(request, 'frontend/topsis_edit.html', {
            'title': 'Edit TOPSIS Calculation',
            'error': error_message,
            'year': datetime.datetime.now().year,
            'is_logged_in': is_logged_in(request)
        })

@csrf_exempt
@require_http_methods(["POST"])
def topsis_update(request, calculation_id):
    """Handle update perhitungan TOPSIS"""
    if not request.session.get('token'):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        # Parse data dari request
        data = json.loads(request.body)
        alternatives = data.get('alternatives', [])
        
        # Validasi data
        if not alternatives:
            return JsonResponse({'error': 'Alternatives data is required'}, status=400)
        
        # Format data sesuai dengan API
        payload = {
            'alternatives': alternatives
        }
        
        # Kirim request ke API
        response = requests.put(
            f'https://benewtopsis-production.up.railway.app/api/topsis/{int(calculation_id)}',
            json=payload,
            cookies={'Authorization': request.session.get('token')},
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            result = response.json()
            return JsonResponse({
                'success': True,
                'message': 'TOPSIS calculation updated successfully',
                'result': result
            })
        else:
            error_data = response.json() if response.content else {}
            return JsonResponse({
                'success': False,
                'error': error_data.get('message', f'Error: {response.status_code}')
            }, status=response.status_code)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def add_alternative(request):
    """Handle penambahan alternatif baru via AJAX"""
    try:
        data = json.loads(request.body)
        criteria = data.get('criteria', {})
        
        # Buat struktur alternatif baru
        new_alternative = {
            'name': f"A{data.get('next_number', 1)}",
            'values': []
        }
        
        # Tambahkan nilai default untuk setiap kriteria
        for criteria_name in criteria.keys():
            new_alternative['values'].append({
                'criteria_name': criteria_name,
                'value': 0.0
            })
        
        return JsonResponse({
            'success': True,
            'alternative': new_alternative
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)