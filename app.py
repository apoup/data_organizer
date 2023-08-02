import csv
import pycountry
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from geopy.geocoders import Nominatim, GoogleV3
import requests
import openai
import phonenumbers
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def read_file_contents(file_contents):
    """
    Read the contents of a CSV file provided as a string and extract data rows.

    Parameters:
        file_contents (str): The content of the CSV file as a string.

    Returns:
        data (list): A list containing rows of data extracted from the CSV file (excluding the header row).
        headers (list): A list containing the headers (first row) of the CSV file.
    """
    # Initialize an empty list to store the data rows extracted from the file
    data = []

    # Split the file_contents into a list of lines using newline as the separator
    lines = file_contents.splitlines()

    # Print the lines extracted from the file (for debugging)
    print(lines, "lines")

    # Create a CSV reader to read the data from the lines
    reader = csv.reader(lines)

    # Read the headers (first row) of the CSV file using the CSV reader
    headers = next(reader)

    # Loop through each row (after the header row) in the CSV file
    for row in reader:
        # Check if the row is not empty (an empty row would be an empty list)
        if row:
            # Append each non-empty row of data to the data list
            data.append(row)

    # Return the extracted data rows (excluding the header row) and the headers
    return data, headers

def country_id(country_name):
    """
    Get the country ID from the given country name using a dictionary.

    Parameters:
        country_name (str): The name of the country.

    Returns:
        int: The country ID corresponding to the given country name, or 0 if the country name is not found in the dictionary.
    """
    country_id = {
        'Galifrey': 1, 'Greece': 2, 'Italy': 3, 'Iraq': 4, 'Honduras': 5,
        'El Salvador': 6, 'Guatemala': 7, 'Jordan': 8, 'Colombia': 9,
        'Mexico': 10, 'Pakistan': 11, 'Niger': 12, 'Kenya': 13,
        'United States': 14, 'Afghanistan': 15, 'Tanzania': 16, 'Burundi': 17,
        'Ecuador': 18, 'Hungary': 19, 'Czechia': 20, 'Bangladesh': 21
    }
    return country_id.get(country_name, 0)  # Return the corresponding country ID or 0 if not found

def get_location_info_from_coordinates(longitude, latitude, info_type):
    """
    Get location information (e.g., address, country, region) from coordinates.

    Parameters:
        longitude (float): The longitude coordinate of the location.
        latitude (float): The latitude coordinate of the location.
        info_type (str): The type of location information to retrieve ('address', 'country', or 'region').

    Returns:
        str or None: The location information if found, or None if the information couldn't be retrieved.
    """
    try:
        # First, try Nominatim API to reverse geocode the coordinates
        geolocator = Nominatim(user_agent="reverse_geocoder")
        location = geolocator.reverse((latitude, longitude), language="en")

        if location:
            print("Using Nominatim API")
            print(location, "nomination")  # Print the location data (for debugging)

            if info_type == "address":
                return location.address  # Return the full address
            elif info_type == "country":
                return location.raw.get("address", {}).get("country", None)  # Return the country name
            elif info_type == "region":
                return location.raw.get("address", {}).get("state", None)  # Return the region/state name

        # If Nominatim API didn't return any results, try Google Maps API
        google_maps_key = "API_KEY"
        google_geolocator = GoogleV3(api_key=google_maps_key)
        location = google_geolocator.reverse((latitude, longitude), exactly_one=True)

        if location:
            print(location, "google")  # Print the location data (for debugging)
            print("Using Google Maps API")

            if info_type == "address":
                return location.address  # Return the full address
            elif info_type == "country":
                return location.raw.get("address_components", {}).get("country", None)  # Return the country name
            elif info_type == "region":
                return location.raw.get("address_components", {}).get("administrative_area_level_1", None)  # Return the region name

        # If Google Maps API didn't return any results, try Mapbox API
        mapbox_token = "API_KEY"
        mapbox_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{longitude},{latitude}.json?access_token={mapbox_token}&language=en"
        response = requests.get(mapbox_url)

        if response.status_code == 200:
            data = response.json()
            if data.get("features"):
                print("Using Mapbox API")
                features = data["features"][0]
                print(features, "mapbox")  # Print the location data (for debugging)

                if info_type == "address":
                    return features["place_name"]  # Return the full address
                elif info_type == "country":
                    country = next(
                        (component["text"] for component in features["context"] if "country" in component["id"]),
                        None
                    )
                    return country  # Return the country name
                elif info_type == "region":
                    region = next(
                        (component["text"] for component in features["context"] if "region" in component["id"]),
                        None
                    )
                    return region  # Return the region name

        # If none of the APIs returned any results, return None
        return None

    except Exception as e:
        print(f"Error occurred during reverse geocoding: {e}")
        return None  # Return None in case of an error during reverse geocoding

def extract_lat_long(input_string):
    pattern = r'^\s*(?P<latitude>[+-]?\d+(\.\d+)?)\s*(?P<symbol>[^\d.]+)\s*(?P<longitude>[+-]?\d+(\.\d+)?)\s*$'
    match = re.match(pattern, input_string)
    if match:
        print(match.group('latitude'), match.group('longitude'), "matched")
        return match.group('latitude'), match.group('longitude')
    else:
        return None

def get_categorized_data(data, categories):

    openai.api_key = 'API_KEY'

    # Generate a list of examples for GPT-3 to understand the categories as options
    category_examples = [f'{category}.' for category in categories]

    prompt = f'You are a language model that categorizes data. Here are the only categories you can choose from, please only use the categories provided and no other information:\n{"".join(category_examples)}\n Now categorize the following data, please only output the category name and no other text:\n"{data}"'
    response = openai.Completion.create(engine="text-davinci-002", prompt=prompt, max_tokens=150)
    categorized_data = response.choices[0].text.strip()
    return categorized_data


def parse_e164(phone_number):
    try:
        # Parse the input phone number using the phonenumbers library
        parsed_number = phonenumbers.parse(phone_number, None)

        # Check if the parsed number is valid and in E.164 format
        if phonenumbers.is_valid_number(parsed_number) and phonenumbers.is_possible_number(parsed_number):
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        else:
            return 0

    except phonenumbers.NumberParseException:
        # Handle exception if the input is not a valid phone number
        return 0


def is_valid_email(email):
    # Regular expression pattern to validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    # Check if the email matches the pattern
    return bool(re.match(email_pattern, email))

def data_organization(data, header_mappings, file_headers, categories):
    # Huge function to handle all data changes and checks and orginization

    # Extract headers that have valid mappings from header_mappings dictionary
    headers = [header for header in header_mappings if header_mappings[header]]

    # If both "Latitude" and "Longitude" are in headers, remove them and add "Country", "Address", and "Region"
    if "Latitude" in headers and "Longitude" in headers:
        headers.remove("Longitude")
        headers.remove("Latitude")

    if "Latitude:Longitude" in headers:
        headers.remove("Latitude:Longitude")

    if "Longitude:Latitude" in headers:
        headers.remove("Longitude:Latitude")

    # Add the "Category" header to the list of headers
    headers.append("Category")

    # Initialize an empty list to store the classified data
    classified_data = []

    # Loop through each row in the data
    for row in data:
        classified_row = []
        for header in headers:
            # Get the matched column for the current header
            matched_column = header_mappings.get(header)
            print("matched_column:", matched_column)
            print("file_headers:", file_headers)
            print("row:", row)
            # Handle the "Country" header if not specified in header_mappings
            if header == 'Country' and header_mappings.get('Country') == "latitude_longitude":
                if header_mappings.get("Longitude") and header_mappings.get("Latitude"):
                    latitude = (row[file_headers.index(header_mappings.get('Latitude'))])
                    longitude = (row[file_headers.index(header_mappings.get('Longitude'))])
                    print(latitude, longitude)
                # if they are in one data point send them to the extract_lat_long functions which regexes the lat long
                elif header_mappings.get("Latitude:Longitude"):
                    map = header_mappings.get('Latitude:Longitude')
                    index = file_headers.index(map)
                    print(index, "index")
                    print(row, "row")
                    data = row[index]
                    latitude, longitude = extract_lat_long(data)
                    print(latitude,longitude,"lat long country")
                else:
                    flash("Latitude and Longitude are incorrect")

                # Get the country name from latitude and longitude using the function get_location_info_from_coordinates
                country_name = get_location_info_from_coordinates(float(longitude), float(latitude), "country")

                # Convert the country name to a country ID using the country_id function
                country = country_id(country_name)

                # If the country ID is 0 (not found in the dictionary), use the country name as is
                if country == 0:
                    country = country_name

                classified_row.append(country)

            # Handle the "Address" header if not specified in header_mappings
            elif header == 'Address' and header_mappings.get('Address') == "latitude_longitude":
                #if lat and long are seperate fine them and store them
                if header_mappings.get("Longitude") and header_mappings.get("Latitude"):
                    latitude = (row[file_headers.index(header_mappings.get('Latitude'))])
                    longitude = (row[file_headers.index(header_mappings.get('Longitude'))])
                    print(latitude, longitude)
                #if they are in one data point send them to the extract_lat_long functions which regexes the lat long
                elif header_mappings.get("Latitude:Longitude"):
                    map = header_mappings.get('Latitude:Longitude')
                    index = file_headers.index(map)
                    print(index, "index")
                    print(row, "row")
                    data = row[index]
                    latitude, longitude = extract_lat_long(data)
                else:
                    flash("Latitude and Longitude are incorrect")

                # Get the address from latitude and longitude using the function get_location_info_from_coordinates
                print(float(longitude),float(latitude),"print test")
                address = get_location_info_from_coordinates(float(longitude), float(latitude), "address")

                classified_row.append(address)

            # Handle the "Region" header if not specified in header_mappings
            elif header == 'Region' and  header_mappings.get('Region') == "latitude_longitude":
                if header_mappings.get("Longitude") and header_mappings.get("Latitude"):
                    latitude= (row[file_headers.index(header_mappings.get('Latitude'))])
                    longitude = (row[file_headers.index(header_mappings.get('Longitude'))])
                    print(latitude, longitude)
                elif header_mappings.get("Latitude:Longitude"):
                    map = header_mappings.get('Latitude:Longitude')
                    index = file_headers.index(map)
                    print(index, "index")
                    print(row, "row")
                    data = row[index]
                    latitude, longitude = extract_lat_long(data)
                else:
                    flash("Latitude and Longitude are incorrect")

                # Get the region from latitude and longitude using the function get_location_info_from_coordinates
                region = get_location_info_from_coordinates(float(longitude), float(latitude), "region")
                classified_row.append(region)

            # Handle the "Category" header and call the function get_categorized_data to categorize the data
            elif header == 'Category':
                # Convert the row data to a comma-separated string for input to get_categorized_data function
                data_to_categorize = ",".join(row)

                # Call the get_categorized_data function to categorize the data
                categorized_data = get_categorized_data(data_to_categorize, categories)

                classified_row.append(categorized_data)

            # Handle the "Contact Phone" header and validate the phone number using the phonenumbers library
            elif header == 'Contact Phone' or header == 'Phone' or header == 'WhatsApp':
                phone_number = row[file_headers.index(matched_column)]
                clean_number = parse_e164(phone_number)
                classified_row.append(clean_number)

            elif header == 'Contact Email' or header == 'Email':
                email =  row[file_headers.index(matched_column)]
                print(email)
                if is_valid_email(email):
                    print("valid email")
                    classified_row.append(email)
            # For all other headers, simply add the corresponding value from the row
            else:
                classified_row.append(row[file_headers.index(matched_column)])

        # Add the classified row to the classified data list
        classified_data.append(classified_row)

    # Insert the headers as the first row in the classified data
    classified_data.insert(0, headers)

    # Return the fully classified data
    return classified_data


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Handles the main page of the web application.

    If a file is uploaded via a POST request, it checks for the file and its validity,
    and then stores the file content in the session. Redirects to the 'column_matching' route.

    Returns:
        rendered template: Renders the 'index.html' template if no file is uploaded.
    """
    if request.method == 'POST':
        file = request.files.get('file')
        print(file)  # Check if the file object is received
        if file is None:
            print("no file uploaded")
            flash('No file was uploaded.')
        else:
            print("File Name: ", file.filename)
            if file.filename == "":
                flash('Please Upload a File')
                return render_template('index.html')
            # elif file.filename[-4]!= ".csv":
            #     flash('Please Upload a Csv')
            #     return render_template('index.html')
            session['file_filename'] = file.filename
            session['file_contents'] = file.read()
            return redirect(url_for('column_matching'))

    return render_template('index.html')

@app.route('/column_matching', methods=['GET', 'POST'])
def column_matching():
    """
    Handles the 'column_matching' page of the web application.

    Reads the uploaded CSV file from the session and displays a form to match CSV headers with predefined columns.

    Returns:
        rendered template: Renders the 'column_matching.html' template with the form to match headers.
    """
    mandatory_headers = ['Latitude', 'Longitude', 'Latitude:Longitude', 'Country', 'Address', 'Region',
                         'Service Name', 'Description', ]
    optional_headers = ['Accessibility', 'Opening Hours', 'Primary Focal Point', 'Consent Form']
    public_contact_information = ['Email', 'Facebook', 'Instagram', 'LinkedIn', 'Phone', 'Signal', 'Skype',
                                  'Telegram', 'TikTok', 'Twitter', 'Viber', 'Website', 'WhatsApp']
    focal_point = ['Contact first Name', 'Contact Last Name', 'Contact Role', 'Contact Email', 'Contact Phone']
    categories = [
        "Accommodation", "Basic Needs", "Children's Services and Protection", "Documentation", "Education",
        "Financial Assistance",
        "Food and Nutrition", "General information", "Health", "Legal Assistance",
        "Mental Health and Psychosocial Support", "Social and Protection Services",
        "Travel", "Women’s Protection and Empowerment", "Work and Employment"]
    file_filename = session.get('file_filename')
    file_contents = session.get('file_contents')
    if file_filename is None or file_contents is None:
        flash('No file was uploaded.')
        print("no work")
        return redirect(url_for('index'))

    file_contents = file_contents.decode('utf-8')
    data, file_headers = read_file_contents(file_contents)
    print(file_headers)
    header_mappings = {}
    for specified_header in mandatory_headers + optional_headers + focal_point + public_contact_information:
        matched_column = request.form.get(specified_header)
        header_mappings[specified_header] = matched_column

    all_matched = all(value is not None for value in header_mappings.values())

    if all_matched:
        classified_data = data_organization(data, header_mappings, file_headers, categories)

        new_file_path = 'organized_data.csv'
        try:
            with open(new_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(classified_data)

            flash('Data has been successfully organized and saved.')
            return redirect(url_for('download'))
        except Exception as e:
            flash(f'Failed to save the organized data: {e}')
            return redirect(url_for('index'))

    return render_template('column_matching.html', mandatory_headers=mandatory_headers,
                           optional_headers=optional_headers, public_contact_information=public_contact_information,
                           focal_point=focal_point, file_headers=file_headers,
                           matched_columns=header_mappings, all_matched=all_matched)

@app.route('/download_organized_data')
def download_organized_data():
    """
    Handles the download of the organized data CSV file.

    Returns:
        file: Sends the 'organized_data.csv' file as an attachment for download.
    """
    organized_data_path = 'organized_data.csv'
    return send_file(organized_data_path, as_attachment=True)

@app.route('/download', methods=['GET'])
def download():
    """
    Handles the 'download' page of the web application.

    Returns:
        rendered template: Renders the 'download.html' template.
    """
    return render_template('download.html')

if __name__ == '__main__':
    app.run(debug=True)
