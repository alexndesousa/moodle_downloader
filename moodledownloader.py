import requests
import bs4
import os
import re


payload = {
    'username': '*',
    'password': '*'
}

with requests.Session() as s:
    p = s.post('https://moodle.port.ac.uk/login/index.php', data=payload)
    p.raise_for_status()
    r = s.get('http://moodle.port.ac.uk/my/')
    r.raise_for_status()
    home = bs4.BeautifulSoup(r.text, features='html.parser')
    course_titles = home.select('.course-list.container-fluid .row.courseovbox.lead div strong a')
    hrefs = [(tag['href'], tag.get_text()) for tag in course_titles]

    for (course_page, course_title) in hrefs:
        page = s.get(course_page)
        page.raise_for_status()
        soup_page = bs4.BeautifulSoup(page.text, features='html.parser')
        course_subsections = [tag['href'] for tag in soup_page.select(".course-content ul li div h3 a[href*=course]")]
        subsection_resources = []

        for subsection in course_subsections:
            sub_page = s.get(subsection)
            sub_page.raise_for_status()
            soup_sub_page = bs4.BeautifulSoup(sub_page.text, features='html.parser')
            sub_resources = [tag['href'] for tag in soup_sub_page.select("a[href*=resource]")]
            sub_file_names = [tag.get_text()[:-5] for tag in soup_sub_page.select("a[href*=resource]")]

            if not sub_resources and not sub_file_names:
                sub_resources = [tag['href'] for tag in soup_sub_page.select("a[href*=pluginfile.php]")]
                sub_file_names = [tag.get_text() for tag in soup_sub_page.select("a[href*=pluginfile.php]")]

            subsection_resources += list(zip(sub_resources, sub_file_names))

        resources = [tag['href'] for tag in soup_page.select("a[href*=resource]")]
        file_names = [tag.get_text()[:-5] for tag in soup_page.select("a[href*=resource]")]
        resources = list(zip(resources, file_names))+subsection_resources

        for (resource, file_name) in set(resources):
            try:
                pre_download_link = s.get(resource)
                pre_download_link.raise_for_status()

                if pre_download_link.headers['content-type'][:9] == 'text/html':
                    pre_download_link = bs4.BeautifulSoup(pre_download_link.text, features='html.parser')
                    pre_download_link = pre_download_link.select("a[href*=pluginfile.php]")[0]['href']
                    pre_download_link = s.get(pre_download_link)
                    pre_download_link.raise_for_status()

                extension = ''
                header = pre_download_link.headers['content-type'][12:]
                if header == 'msword' or header == 'vnd.openxmlformats-officedocument.wordprocessingml.document':
                    extension = '.doc'
                elif header == 'pdf':
                    extension = '.pdf'
                elif header == 'vnd.ms-powerpoint' or header == 'vnd.openxmlformats-officedocument.presentationml.presentation':
                    extension = '.ppt'
                elif header == 'zip':
                    extension = '.zip'
                elif pre_download_link.headers['content-type'][:10] == 'text/plain':
                    extension = '.txt'
                elif pre_download_link.headers['content-type'][:9] == 'text/html':
                    extension = '.html'
                elif header == 'x-tex':
                    extension = '.tex'

                file_re = re.compile(r'[/?<>\\:*|\"]')
                file_name = re.sub(file_re, '-', file_name)

                os.makedirs(course_title, exist_ok=True)
                download_file = open(os.path.join(course_title, file_name+extension), 'wb')

                for chunk in pre_download_link.iter_content(100000):
                    download_file.write(chunk)

                download_file.close()
            except IndexError:
                print('Unable to find file. Skipping.')

